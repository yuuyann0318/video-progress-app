"""
リール / SNS投稿管理 — Google Sheets 操作レイヤー

ReelPosts シートに対する CRUD を担当。
- リール投稿の新規登録・更新・取得
- アナリティクス（再生数/いいね/保存等）の更新
- 投稿スケジュール管理
"""

import warnings
warnings.filterwarnings("ignore")

import uuid
from datetime import datetime
from typing import Optional

import gspread
from gspread import Cell
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

from utils.config import (
    SPREADSHEET_ID, CREDENTIALS_PATH, SCOPES,
    REEL_SHEET_NAME, REEL_HEADERS, REEL_ANALYTICS_COLS,
)
from utils.sheets import _get_credentials


# ─── 接続 ─────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="📡 リールシートに接続中...")
def _get_reel_sheet() -> gspread.Worksheet:
    try:
        creds = _get_credentials()
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            return spreadsheet.worksheet(REEL_SHEET_NAME)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(
                title=REEL_SHEET_NAME, rows=2000, cols=len(REEL_HEADERS) + 5
            )
            sheet.append_row(REEL_HEADERS)
            return sheet
    except FileNotFoundError:
        st.error("❌ `credentials.json` が見つかりません。")
        st.stop()
    except Exception as e:
        st.error(f"❌ リールシート接続エラー: {e}")
        st.stop()


def ensure_reel_headers() -> None:
    """リールシートのヘッダーを確認・修正する"""
    sheet = _get_reel_sheet()
    existing = sheet.row_values(1)
    if not existing:
        sheet.update("A1", [REEL_HEADERS])
    elif existing != REEL_HEADERS:
        # 既存データを保持しながらヘッダーを更新
        sheet.update("A1", [REEL_HEADERS])


# ─── データ取得 ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner="📱 リールデータを読み込み中...")
def load_reels() -> pd.DataFrame:
    """全リールデータを取得して DataFrame で返す（30秒TTLキャッシュ）"""
    sheet = _get_reel_sheet()
    try:
        records = sheet.get_all_records(expected_headers=REEL_HEADERS)
    except Exception:
        records = sheet.get_all_records()

    if not records:
        df_empty = pd.DataFrame(columns=REEL_HEADERS)
        # 空DataFrameでも日付列は datetime64 型にしておく（.dt アクセッサ対応）
        for date_col in ["投稿予定日", "投稿済み日", "最終更新日時"]:
            df_empty[date_col] = pd.Series(dtype="datetime64[ns]")
        for num_col in REEL_ANALYTICS_COLS:
            df_empty[num_col] = pd.Series(dtype="int64")
        return df_empty

    df = pd.DataFrame(records)

    # 存在しないカラムを補完
    for col in REEL_HEADERS:
        if col not in df.columns:
            df[col] = ""

    # 管理番号: 文字列
    df["管理番号"] = (
        df["管理番号"].astype(str).str.strip()
        .replace({"nan": "", "None": "", "0": "", "0.0": ""})
    )

    # ID: 文字列
    df["ID"] = df["ID"].astype(str).str.strip()

    # 日付型変換
    df["投稿予定日"] = pd.to_datetime(df["投稿予定日"], errors="coerce")
    df["投稿済み日"] = pd.to_datetime(df["投稿済み日"], errors="coerce")
    df["最終更新日時"] = pd.to_datetime(df["最終更新日時"], errors="coerce")

    # アナリティクス数値型変換
    for col in REEL_ANALYTICS_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df[REEL_HEADERS]


def clear_reel_cache() -> None:
    """リールデータキャッシュをクリア"""
    load_reels.clear()


# ─── データ追加 ────────────────────────────────────────────────────────────────

def add_reel(data: dict) -> str:
    """
    新規リールを1行追加する。
    - ID は自動生成
    - 最終更新日時 は自動セット
    Returns: 生成されたID
    """
    sheet = _get_reel_sheet()

    reel_id = _generate_reel_id()
    data["ID"] = reel_id
    data["最終更新日時"] = _now()

    # 未設定のアナリティクスは0
    for col in REEL_ANALYTICS_COLS:
        if not data.get(col):
            data[col] = "0"

    row = [str(data.get(h, "")) for h in REEL_HEADERS]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    clear_reel_cache()
    return reel_id


# ─── データ更新 ────────────────────────────────────────────────────────────────

def update_reel(reel_id: str, updates: dict) -> None:
    """
    ID を key に対象行を特定し、指定カラムをバッチ更新する。
    """
    sheet = _get_reel_sheet()
    all_values = sheet.get_all_values()

    if not all_values:
        raise ValueError("リールシートにデータがありません")

    header_row = all_values[0]

    if "ID" not in header_row:
        raise ValueError("ヘッダーに 'ID' カラムが見つかりません")

    id_col_idx = header_row.index("ID")

    target_row_idx = None
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col_idx and row[id_col_idx].strip() == reel_id.strip():
            target_row_idx = i
            break

    if target_row_idx is None:
        raise ValueError(f"ID '{reel_id}' のリールが見つかりません")

    updates["最終更新日時"] = _now()
    col_map = {h: idx + 1 for idx, h in enumerate(header_row)}

    cells = []
    for col_name, value in updates.items():
        if col_name in col_map:
            cells.append(Cell(target_row_idx, col_map[col_name], str(value)))

    if cells:
        sheet.update_cells(cells, value_input_option="USER_ENTERED")

    clear_reel_cache()


# ─── アナリティクス更新 ────────────────────────────────────────────────────────

def update_reel_analytics(reel_id: str, analytics: dict) -> None:
    """
    投稿済みリールのアナリティクス（再生数等）を更新する。
    analytics: {"再生数": 10000, "いいね数": 500, ...}
    """
    update_reel(reel_id, analytics)


# ─── ユーティリティ ────────────────────────────────────────────────────────────

def _generate_reel_id() -> str:
    return "RL-" + str(uuid.uuid4()).replace("-", "")[:10].upper()


def generate_reel_id() -> str:
    return _generate_reel_id()


def _now() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M")
