"""
リサーチ機能 — Google Sheets 操作レイヤー

ResearchItems シートに対する CRUD を担当。
- YouTubeサムネイルURL生成
- リサーチ提出・評価・案件化の一連フローをサポート
"""

import warnings
warnings.filterwarnings("ignore")

import re
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
    RESEARCH_SHEET_NAME, RESEARCH_HEADERS,
)
from utils.sheets import _get_credentials


# ─── 接続 ─────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="📡 リサーチシートに接続中...")
def _get_research_sheet() -> gspread.Worksheet:
    try:
        creds = _get_credentials()
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            return spreadsheet.worksheet(RESEARCH_SHEET_NAME)
        except gspread.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(
                title=RESEARCH_SHEET_NAME, rows=2000, cols=len(RESEARCH_HEADERS) + 2
            )
            sheet.append_row(RESEARCH_HEADERS)
            return sheet
    except FileNotFoundError:
        st.error("❌ `credentials.json` が見つかりません。")
        st.stop()
    except Exception as e:
        st.error(f"❌ リサーチシート接続エラー: {e}")
        st.stop()


def ensure_research_headers() -> None:
    """リサーチシートのヘッダーを確認・修正する"""
    sheet = _get_research_sheet()
    existing = sheet.row_values(1)
    if not existing:
        sheet.update("A1", [RESEARCH_HEADERS])
    elif existing != RESEARCH_HEADERS:
        sheet.update("A1", [RESEARCH_HEADERS])


# ─── データ取得 ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner="🔍 リサーチデータを読み込み中...")
def load_research() -> pd.DataFrame:
    """全リサーチデータを取得して DataFrame で返す"""
    sheet = _get_research_sheet()
    try:
        records = sheet.get_all_records(expected_headers=RESEARCH_HEADERS)
    except Exception:
        records = sheet.get_all_records()

    if not records:
        return pd.DataFrame(columns=RESEARCH_HEADERS)

    df = pd.DataFrame(records)
    for col in RESEARCH_HEADERS:
        if col not in df.columns:
            df[col] = ""

    df["提出日時"] = pd.to_datetime(df["提出日時"], errors="coerce")
    return df[RESEARCH_HEADERS]


def clear_research_cache() -> None:
    load_research.clear()


# ─── データ追加 ────────────────────────────────────────────────────────────────

def add_research(data: dict) -> None:
    """リサーチを1件追加する"""
    sheet = _get_research_sheet()
    data["リサーチID"]    = _generate_id()
    data["提出日時"]      = _now()
    data["評価ステータス"] = data.get("評価ステータス", "未評価")
    data["案件ID"]        = ""

    row = [str(data.get(h, "")) for h in RESEARCH_HEADERS]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    clear_research_cache()


# ─── 評価更新 ─────────────────────────────────────────────────────────────────

def evaluate_research(research_id: str, status: str, reviewer: str, comment: str) -> None:
    """リサーチの評価（採用/不採用）を更新する"""
    _update_research(research_id, {
        "評価ステータス": status,
        "評価者":         reviewer,
        "評価コメント":   comment,
    })


def link_project(research_id: str, project_id: str) -> None:
    """採用済みリサーチに案件IDを紐付ける"""
    _update_research(research_id, {"案件ID": project_id})


# ─── 内部更新ヘルパー ─────────────────────────────────────────────────────────

def _update_research(research_id: str, updates: dict) -> None:
    sheet = _get_research_sheet()
    all_values = sheet.get_all_values()

    if not all_values:
        raise ValueError("リサーチシートが空です")

    header_row = all_values[0]
    if "リサーチID" not in header_row:
        raise ValueError("ヘッダーに 'リサーチID' が見つかりません")

    id_col_idx = header_row.index("リサーチID")
    target_row_idx = None
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > id_col_idx and row[id_col_idx].strip() == research_id.strip():
            target_row_idx = i
            break

    if target_row_idx is None:
        raise ValueError(f"リサーチID '{research_id}' が見つかりません")

    col_map = {h: idx + 1 for idx, h in enumerate(header_row)}
    cells = []
    for col_name, value in updates.items():
        if col_name in col_map:
            cells.append(Cell(target_row_idx, col_map[col_name], str(value)))

    if cells:
        sheet.update_cells(cells, value_input_option="USER_ENTERED")

    clear_research_cache()


# ─── YouTube ユーティリティ ────────────────────────────────────────────────────

def extract_youtube_id(url: str) -> Optional[str]:
    """YouTubeのURLからビデオIDを抽出する"""
    if not url:
        return None
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_\-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_\-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_\-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def youtube_thumbnail(video_id: str, quality: str = "mq") -> str:
    """YouTubeサムネイルURLを返す（quality: mq=320x180, hq=480x360）"""
    return f"https://img.youtube.com/vi/{video_id}/{quality}default.jpg"


def is_youtube_url(url: str) -> bool:
    return extract_youtube_id(url) is not None


# ─── ユーティリティ ────────────────────────────────────────────────────────────

def _generate_id() -> str:
    return "R-" + str(uuid.uuid4()).replace("-", "")[:10].upper()


def _now() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M")
