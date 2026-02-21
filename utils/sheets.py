"""
Google Sheets 操作レイヤー

設計方針:
- _get_credentials(): ローカルは credentials.json、クラウドは st.secrets を自動判定
- _get_sheet()      : 接続オブジェクトをキャッシュ（アプリ起動中は再接続しない）
- load_data()       : 全データを30秒TTLでキャッシュ（大量データでも高速表示）
- update_row()      : セルをバッチ更新（API呼び出しを最小化）
- ensure_headers()  : 起動時にヘッダー構造を自動修復
"""

import warnings
warnings.filterwarnings("ignore")

import gspread
from gspread import Cell
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime
import uuid

from utils.config import (
    SPREADSHEET_ID, SHEET_NAME, CREDENTIALS_PATH,
    SCOPES, HEADERS,
)


# ─── 接続 ─────────────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    """
    認証情報を取得する。
    - Streamlit Cloud / .streamlit/secrets.toml がある場合:
        st.secrets["gcp_service_account"] を使用
    - ローカル開発:
        credentials.json ファイルを使用（フォールバック）
    """
    try:
        if "gcp_service_account" in st.secrets:
            info = {k: v for k, v in st.secrets["gcp_service_account"].items()}
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass
    return Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)


@st.cache_resource(show_spinner="📡 スプレッドシートに接続中...")
def _get_sheet() -> gspread.Worksheet:
    try:
        creds = _get_credentials()
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet.worksheet(SHEET_NAME)
    except FileNotFoundError:
        st.error("❌ `credentials.json` が見つかりません。ファイルを配置するか Secrets を設定してください。")
        st.stop()
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ スプレッドシートが見つかりません。IDを確認してください。")
        st.stop()
    except gspread.exceptions.APIError as e:
        st.error(f"❌ API エラー（スプレッドシートの共有設定を確認してください）: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ 接続エラー: {e}")
        st.stop()


# ─── データ取得 ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner="📊 データを読み込み中...")
def load_data() -> pd.DataFrame:
    """
    全案件データを取得して DataFrame で返す。
    get_all_values() ベースで実装し、空ヘッダー・重複ヘッダー問題を根本回避。
    30秒 TTL キャッシュ付き。
    """
    sheet = _get_sheet()
    all_values = sheet.get_all_values()

    if not all_values:
        return pd.DataFrame(columns=HEADERS)

    raw_header = all_values[0]
    data_rows  = all_values[1:]

    if not data_rows:
        return pd.DataFrame(columns=HEADERS)

    # 空ヘッダーセルを無視して辞書リストを構築
    records = []
    for row in data_rows:
        # 行が全て空なら読み飛ばす
        if not any(v.strip() for v in row):
            continue
        record = {}
        for i, h in enumerate(raw_header):
            h = h.strip()
            if h:  # 空のヘッダーセルは無視
                record[h] = row[i].strip() if i < len(row) else ""
        records.append(record)

    if not records:
        return pd.DataFrame(columns=HEADERS)

    df = pd.DataFrame(records)

    # 存在しないカラムを補完（列追加後の旧データとの互換性）
    for col in HEADERS:
        if col not in df.columns:
            df[col] = ""

    # 管理番号: 文字列として扱い、空・ゼロは空文字に統一
    df["管理番号"] = (
        df["管理番号"].astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "0": "", "0.0": ""})
    )

    # ID: 文字列
    df["ID"] = df["ID"].astype(str).str.strip()

    # 日付型変換（不正値は NaT）
    for date_col in ["納期", "台本提出期限", "台本提出日", "動画提出期限", "動画提出日"]:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    return df[HEADERS]


def clear_cache() -> None:
    """データキャッシュをクリア（更新後に必ず呼ぶ）"""
    load_data.clear()


# ─── データ追加 ────────────────────────────────────────────────────────────────

def add_row(data: dict) -> None:
    """
    新規案件を1行追加する。
    - ID は自動生成
    - 最終更新日時 は自動セット
    """
    sheet = _get_sheet()

    if not data.get("ID"):
        data["ID"] = _generate_id()
    data["最終更新日時"] = _now()

    row = [str(data.get(h, "")) for h in HEADERS]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    clear_cache()


# ─── データ更新 ────────────────────────────────────────────────────────────────

def update_row(row_id: str, updates: dict) -> None:
    """
    ID を key に対象行を特定し、指定カラムをバッチ更新する。
    update_cells() で API 呼び出しを1回に集約。
    """
    sheet = _get_sheet()
    all_values = sheet.get_all_values()

    if not all_values:
        raise ValueError("シートにデータがありません")

    header_row = all_values[0]

    # ID カラムのインデックスを動的に取得（カラム追加に強い設計）
    if "ID" not in header_row:
        raise ValueError("ヘッダーに 'ID' カラムが見つかりません")
    id_col_idx = header_row.index("ID")

    # 対象行を線形探索（gspread に範囲指定クエリがないため）
    target_row_idx = None
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col_idx and row[id_col_idx].strip() == row_id.strip():
            target_row_idx = i
            break

    if target_row_idx is None:
        raise ValueError(f"ID '{row_id}' の案件が見つかりません")

    updates["最終更新日時"] = _now()
    col_map = {h: idx + 1 for idx, h in enumerate(header_row)}

    # バッチ更新リストを作成
    cells = []
    for col_name, value in updates.items():
        if col_name in col_map:
            cells.append(Cell(target_row_idx, col_map[col_name], str(value)))

    if cells:
        sheet.update_cells(cells, value_input_option="USER_ENTERED")

    clear_cache()


# ─── ヘッダー保守 ─────────────────────────────────────────────────────────────

def _col_letter(n: int) -> str:
    """列番号（1始まり）をアルファベット表記に変換（例: 1→A, 27→AA）"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def ensure_headers() -> None:
    """
    スプレッドシートのヘッダーが HEADERS と一致しているか確認・修正する。
    アプリ起動時に1回だけ呼ぶこと。
    - 新カラム追加後の自動マイグレーション対応
    - 旧ヘッダー行の余剰列（空セル）を自動クリアし重複 '' エラーを防止
    """
    sheet = _get_sheet()
    existing = sheet.row_values(1)

    if existing == HEADERS:
        return  # 最新状態なので何もしない

    if not existing:
        sheet.update("A1", [HEADERS])
        return

    # 新しい HEADERS をA1から書き込む
    sheet.update("A1", [HEADERS])

    # 旧ヘッダーが HEADERS より多い列を持つ場合、余剰セルをクリア
    # （空文字の重複ヘッダーが残ると get_all_records が GSpreadException を出すため）
    if len(existing) > len(HEADERS):
        start_letter = _col_letter(len(HEADERS) + 1)
        end_letter   = _col_letter(len(existing))
        sheet.batch_clear([start_letter + "1:" + end_letter + "1"])


# ─── ユーティリティ ────────────────────────────────────────────────────────────

def generate_id() -> str:
    """外部から呼び出し可能なID生成関数"""
    return str(uuid.uuid4()).replace("-", "")[:12].upper()


def _generate_id() -> str:
    return generate_id()


def _now() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M")
