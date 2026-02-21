"""
共通UIコンポーネント — プレミアムデザインシステム

■ デザイン原則
  - 一目で状態が分かる：ステータスカラーを全コンポーネントで統一
  - スキャン優先：テキストより視覚（バッジ・バー・色）
  - 情報密度：カードに必要情報を凝縮し、余白は最小化
  - 緊急性の視覚化：期限まで日数を常にカラーバッジで表示
"""

import calendar as _cal_module
import streamlit as st
import pandas as pd
from collections import defaultdict
from datetime import date, timedelta
from typing import List, Dict, Optional

from utils.config import (
    STATUSES, STATUS_EMOJI, STATUS_BG, STATUS_TEXT_COLOR, PAGE_SIZE,
    REEL_STATUS_EMOJI, REEL_STATUS_BG, REEL_STATUS_TEXT,
    PLATFORM_EMOJI, PLATFORM_COLOR,
)


# ─── グローバルCSS ─────────────────────────────────────────────────────────────

GLOBAL_CSS = """
<style>
/* ━━━ ベース ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ━━━ サイドバー ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label { color: #cbd5e1 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #f8fafc !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.1) !important; }
[data-testid="stSidebar"] .stTextInput > div {
    background: #1e293b !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stTextInput input {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #f1f5f9 !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stTextInput input::placeholder {
    color: rgba(255,255,255,0.35) !important;
}
[data-testid="stSidebar"] .stCheckbox span { color: #94a3b8 !important; }

/* ━━━ メインコンテンツ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

/* ━━━ ステータスバッジ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.78em;
    font-weight: 700;
    letter-spacing: 0.01em;
    white-space: nowrap;
}

/* ━━━ プレミアム案件カード ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.proj-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: box-shadow 0.18s ease, transform 0.18s ease;
    position: relative;
    overflow: hidden;
}
.proj-card:hover {
    box-shadow: 0 6px 20px rgba(0,0,0,0.09);
    transform: translateY(-1px);
}
.proj-card.selected {
    background: #f0f7ff;
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.3);
}
.proj-card-stripe {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    border-radius: 12px 0 0 12px;
}
.proj-card-inner { padding-left: 8px; }
.proj-card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 7px;
}
.proj-card-title {
    font-weight: 800;
    font-size: 0.97em;
    color: #0f172a;
    line-height: 1.35;
    margin-bottom: 7px;
}
.proj-card-meta {
    display: flex;
    gap: 14px;
    font-size: 0.8em;
    color: #64748b;
    margin-bottom: 7px;
    flex-wrap: wrap;
}
.proj-card-subs {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}

/* ━━━ パイプラインバー ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.pipeline-wrap {
    margin: 10px 0;
}
.pipeline-bar {
    display: flex;
    border-radius: 10px;
    overflow: hidden;
    height: 42px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.pipeline-seg {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: filter 0.2s;
    cursor: default;
}
.pipeline-seg:hover { filter: brightness(1.1); }
.pipeline-seg-count { color: white; font-weight: 900; font-size: 1em; line-height: 1; }
.pipeline-seg-emoji { color: rgba(255,255,255,0.85); font-size: 0.65em; line-height: 1.2; }
.pipeline-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 8px;
}
.pipeline-legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.78em;
    font-weight: 600;
}
.pipeline-legend-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
}

/* ━━━ カンバンボード ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.kanban-scroll {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    padding: 4px 2px 14px;
    scrollbar-width: thin;
    scrollbar-color: #cbd5e1 transparent;
}
.kanban-col {
    min-width: 210px;
    max-width: 220px;
    background: #f8fafc;
    border-radius: 12px;
    padding: 12px;
    flex-shrink: 0;
    border: 1px solid #e2e8f0;
}
.kanban-col-hdr {
    font-weight: 700;
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 10px;
    padding-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.kanban-count {
    border-radius: 999px;
    padding: 1px 7px;
    font-size: 0.88em;
    color: white;
    font-weight: 700;
}
.kanban-card {
    background: white;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
    border: 1px solid #e2e8f0;
    border-left: 3px solid;
    font-size: 0.82em;
}
.kanban-card-title {
    font-weight: 700;
    color: #0f172a;
    line-height: 1.3;
    margin-bottom: 5px;
    word-break: break-all;
}
.kanban-card-meta {
    color: #64748b;
    font-size: 0.9em;
    margin-bottom: 3px;
}
.kanban-empty {
    text-align: center;
    color: #cbd5e1;
    padding: 18px 0;
    font-size: 0.83em;
}

/* ━━━ 緊急タスクカード ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.alert-card {
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border-left: 4px solid;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.alert-icon { font-size: 1.3em; flex-shrink: 0; }
.alert-body { flex: 1; }
.alert-title { font-weight: 700; font-size: 0.92em; margin-bottom: 2px; }
.alert-sub { font-size: 0.8em; opacity: 0.75; }

/* ━━━ KPIカード ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.kpi-card {
    background: white;
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.kpi-value {
    font-size: 2.4em;
    font-weight: 900;
    line-height: 1;
    margin-bottom: 4px;
}
.kpi-label {
    font-size: 0.82em;
    color: #64748b;
    font-weight: 500;
}

/* ━━━ ページネーション ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.pagination-info {
    text-align: center;
    color: #64748b;
    font-size: 0.88em;
    padding: 6px 0;
}

/* ━━━ セクションタイトル ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.section-title {
    font-size: 0.72em;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #94a3b8;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid #e2e8f0;
}

/* ━━━ カレンダー ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.cal-wrap { font-family: inherit; }
.cal-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1px;
    background: #cbd5e1;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.cal-hdr {
    background: #1e3a5f;
    color: white;
    text-align: center;
    padding: 10px 4px;
    font-weight: 700;
    font-size: 0.82em;
    letter-spacing: 0.05em;
}
.cal-hdr.sat { background: #2563eb; }
.cal-hdr.sun { background: #dc2626; }
.cal-cell {
    background: white;
    min-height: 90px;
    padding: 6px 5px;
    font-size: 0.82em;
}
.cal-cell.today  { background: #eff6ff; }
.cal-cell.past   { background: #f8fafc; }
.cal-cell.empty  { background: #f1f5f9; min-height: 90px; }
.cal-cell.sat .cal-dn { color: #2563eb; }
.cal-cell.sun .cal-dn { color: #dc2626; }
.cal-dn {
    font-weight: 800;
    font-size: 0.95em;
    color: #374151;
    margin-bottom: 3px;
    display: inline-block;
}
.cal-dn.today-circle {
    background: #3b82f6;
    color: white;
    border-radius: 50%;
    width: 22px; height: 22px;
    text-align: center;
    line-height: 22px;
    display: inline-block;
}
.cal-ev {
    font-size: 0.72em;
    padding: 2px 4px;
    border-radius: 4px;
    margin-bottom: 2px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    display: block;
    max-width: 100%;
}
.cal-ev.deadline-over  { background:#fee2e2; color:#991b1b; border-left:3px solid #ef4444; }
.cal-ev.deadline-soon  { background:#fef9c3; color:#92400e; border-left:3px solid #f59e0b; }
.cal-ev.deadline-ok    { background:#d1fae5; color:#065f46; border-left:3px solid #10b981; }
.cal-ev.reel-sched     { background:#fce7f3; color:#9d174d; border-left:3px solid #e1306c; }
.cal-ev.reel-posted    { background:#d1fae5; color:#065f46; border-left:3px solid #10b981; }
.cal-ev-more { font-size:0.68em; color:#94a3b8; padding:1px 4px; }
</style>
"""


def inject_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ─── 内部ユーティリティ ────────────────────────────────────────────────────────

def _deadline_pill(due_date, today: pd.Timestamp) -> str:
    """期限をカラーピルバッジHTMLで返す"""
    if pd.isna(due_date):
        return '<span style="font-size:0.75em;color:#94a3b8;">期限なし</span>'
    delta = int((due_date - today).days)
    if delta < 0:
        bg, color, text = "#fee2e2", "#991b1b", str(abs(delta)) + "日超過"
    elif delta == 0:
        bg, color, text = "#fee2e2", "#991b1b", "本日締切"
    elif delta <= 3:
        bg, color, text = "#ffedd5", "#9a3412", "あと" + str(delta) + "日"
    elif delta <= 7:
        bg, color, text = "#fef9c3", "#92400e", "あと" + str(delta) + "日"
    else:
        bg, color, text = "#d1fae5", "#065f46", "あと" + str(delta) + "日"
    return (
        '<span style="background:' + bg + ';color:' + color + ';'
        'padding:2px 9px;border-radius:999px;font-size:0.74em;font-weight:700;">'
        '📅 ' + text + '</span>'
    )


def _mini_sub_badge(label: str, sub_date, deadline, today: pd.Timestamp) -> str:
    """提出ステータスをミニバッジHTMLで返す"""
    has_sub = pd.notna(sub_date)
    has_dl  = pd.notna(deadline)

    if has_sub:
        return (
            '<span style="background:#d1fae5;color:#065f46;'
            'padding:1px 7px;border-radius:999px;font-size:0.72em;font-weight:700;">'
            + label + ' ✅</span>'
        )
    if has_dl and deadline < today:
        return (
            '<span style="background:#fee2e2;color:#991b1b;'
            'padding:1px 7px;border-radius:999px;font-size:0.72em;font-weight:700;">'
            + label + ' 🔴</span>'
        )
    if has_dl:
        return (
            '<span style="background:#fef9c3;color:#92400e;'
            'padding:1px 7px;border-radius:999px;font-size:0.72em;font-weight:700;">'
            + label + ' 🟡</span>'
        )
    return (
        '<span style="background:#f3f4f6;color:#6b7280;'
        'padding:1px 7px;border-radius:999px;font-size:0.72em;font-weight:600;">'
        + label + ' ➖</span>'
    )


# ─── ステータスバッジ ──────────────────────────────────────────────────────────

def status_badge_html(status: str) -> str:
    emoji = STATUS_EMOJI.get(status, "")
    bg    = STATUS_BG.get(status, "#f3f4f6")
    color = STATUS_TEXT_COLOR.get(status, "#374151")
    return (
        '<span class="status-badge" style="background:' + bg + ';color:' + color + ';">'
        + emoji + ' ' + status + '</span>'
    )


def reel_status_badge_html(status: str) -> str:
    emoji = REEL_STATUS_EMOJI.get(status, "")
    bg    = REEL_STATUS_BG.get(status, "#f3f4f6")
    color = REEL_STATUS_TEXT.get(status, "#374151")
    return (
        '<span class="status-badge" style="background:' + bg + ';color:' + color + ';">'
        + emoji + ' ' + status + '</span>'
    )


def platform_badge_html(platform: str) -> str:
    emoji = PLATFORM_EMOJI.get(platform, "📲")
    color = PLATFORM_COLOR.get(platform, "#7c3aed")
    return (
        '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        'font-size:0.78em;font-weight:700;color:white;background:' + color + ';">'
        + emoji + ' ' + platform + '</span>'
    )


# ─── 残り日数 ─────────────────────────────────────────────────────────────────

def days_label(due_date) -> str:
    if pd.isna(due_date):
        return "—"
    today = pd.Timestamp(date.today())
    delta = int((due_date - today).days)
    if delta < 0:
        return "🔴 **" + str(abs(delta)) + "日超過**"
    elif delta == 0:
        return "🔴 **本日締切**"
    elif delta <= 3:
        return "🟠 あと **" + str(delta) + "日**"
    elif delta <= 7:
        return "🟡 あと **" + str(delta) + "日**"
    else:
        return "🟢 あと " + str(delta) + "日"


# ─── ページネーション ──────────────────────────────────────────────────────────

def paginate(df: pd.DataFrame, page_size: int = PAGE_SIZE, key: str = "page") -> pd.DataFrame:
    total = len(df)
    if total == 0:
        return df

    total_pages = max(1, (total + page_size - 1) // page_size)
    session_key = "_page_" + key
    if session_key not in st.session_state:
        st.session_state[session_key] = 1
    if st.session_state[session_key] > total_pages:
        st.session_state[session_key] = 1

    col_prev, col_info, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("◀", key=key + "_prev", disabled=st.session_state[session_key] <= 1):
            st.session_state[session_key] -= 1
            st.rerun()
    with col_info:
        current = st.session_state[session_key]
        start = (current - 1) * page_size + 1
        end   = min(current * page_size, total)
        st.markdown(
            '<div class="pagination-info">全 <b>' + str(total) + '</b> 件中 '
            '<b>' + str(start) + '〜' + str(end) + '</b> 件表示'
            '（' + str(current) + '/' + str(total_pages) + ' ページ）</div>',
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("▶", key=key + "_next", disabled=st.session_state[session_key] >= total_pages):
            st.session_state[session_key] += 1
            st.rerun()

    page = st.session_state[session_key]
    return df.iloc[(page - 1) * page_size: page * page_size]


# ─── パイプラインバー ──────────────────────────────────────────────────────────

def render_pipeline_bar(df: pd.DataFrame) -> None:
    """ステータス別の案件数をビジュアルパイプラインバーで表示"""
    if df.empty:
        return

    counts = df["ステータス"].value_counts()
    total  = len(df)

    bar_html  = '<div class="pipeline-bar">'
    leg_html  = '<div class="pipeline-legend">'

    has_any = False
    for status in STATUSES:
        n = int(counts.get(status, 0))
        if n == 0:
            continue
        has_any = True
        pct   = n / total * 100
        color = STATUS_TEXT_COLOR.get(status, "#6b7280")
        emoji = STATUS_EMOJI.get(status, "")
        title = status + ": " + str(n) + "件"

        bar_html += (
            '<div class="pipeline-seg" style="flex:' + str(pct) + ';min-width:32px;background:' + color + ';"'
            ' title="' + title + '">'
            '<span class="pipeline-seg-count">' + str(n) + '</span>'
            '<span class="pipeline-seg-emoji">' + emoji + '</span>'
            '</div>'
        )
        leg_html += (
            '<span class="pipeline-legend-item" style="color:' + color + ';">'
            '<span class="pipeline-legend-dot" style="background:' + color + ';"></span>'
            + emoji + ' ' + status + ' (' + str(n) + ')'
            '</span>'
        )

    bar_html += '</div>'
    leg_html += '</div>'

    if has_any:
        st.markdown(
            '<div class="pipeline-wrap">' + bar_html + leg_html + '</div>',
            unsafe_allow_html=True,
        )


# ─── カンバンボード ────────────────────────────────────────────────────────────

def render_kanban_board(df: pd.DataFrame) -> None:
    """HTMLカンバンボードを描画（読み取り専用ビジュアル）"""
    if df.empty:
        st.info("案件がありません。")
        return

    today = pd.Timestamp(date.today())
    html  = '<div class="kanban-scroll">'

    for status in STATUSES:
        sub_df = df[df["ステータス"] == status]
        n      = len(sub_df)
        color  = STATUS_TEXT_COLOR.get(status, "#6b7280")
        emoji  = STATUS_EMOJI.get(status, "")

        html += (
            '<div class="kanban-col">'
            '<div class="kanban-col-hdr" style="color:' + color + ';border-bottom:2px solid ' + color + ';">'
            + emoji + ' ' + status +
            '<span class="kanban-count" style="background:' + color + ';">' + str(n) + '</span>'
            '</div>'
        )

        if n == 0:
            html += '<div class="kanban-empty">案件なし</div>'
        else:
            for _, row in sub_df.iterrows():
                title  = str(row.get("案件名", "") or "")
                mgmt   = str(row.get("管理番号", "") or "")
                due    = row.get("納期")
                writer = str(row.get("担当台本作家", "") or "—")
                editor = str(row.get("担当編集者", "") or "—")

                dl_color = "#10b981"
                dl_text  = "期限なし"
                if pd.notna(due):
                    delta = int((due - today).days)
                    if delta < 0:
                        dl_color = "#ef4444"
                        dl_text  = str(abs(delta)) + "日超過"
                    elif delta == 0:
                        dl_color = "#ef4444"
                        dl_text  = "本日締切"
                    elif delta <= 3:
                        dl_color = "#f97316"
                        dl_text  = "あと" + str(delta) + "日"
                    elif delta <= 7:
                        dl_color = "#eab308"
                        dl_text  = "あと" + str(delta) + "日"
                    else:
                        dl_color = "#10b981"
                        dl_text  = "あと" + str(delta) + "日"

                mgmt_str = ("[" + mgmt + "] ") if mgmt else ""
                short    = title[:22] + ("…" if len(title) > 22 else "")

                html += (
                    '<div class="kanban-card" style="border-left-color:' + color + ';">'
                    '<div class="kanban-card-title">'
                    '<span style="color:#94a3b8;font-size:0.85em;">' + mgmt_str + '</span>'
                    + short +
                    '</div>'
                    '<div class="kanban-card-meta">✏️ ' + writer + '　🎬 ' + editor + '</div>'
                    '<span style="font-size:0.75em;color:' + dl_color + ';font-weight:600;">'
                    '📅 ' + dl_text + '</span>'
                    '</div>'
                )

        html += '</div>'

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─── テーブル表示（管理者用フル版）────────────────────────────────────────────

def render_table(df: pd.DataFrame, key: str = "main_table") -> pd.DataFrame:
    if df.empty:
        st.info("該当する案件がありません。")
        return pd.DataFrame()

    paged = paginate(df, key=key)

    disp = paged.copy()
    disp["残り日数"] = disp["納期"].apply(days_label)
    disp["納期表示"] = disp["納期"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notna(x) else "—")
    disp["ステータス表示"] = disp["ステータス"].apply(
        lambda s: STATUS_EMOJI.get(s, "") + " " + s
    )
    # 提出状況
    today_ts = pd.Timestamp(date.today())
    def _sub_icon(sub, dl):
        if pd.notna(sub):
            return "✅"
        if pd.notna(dl) and dl < today_ts:
            return "🔴"
        if pd.notna(dl):
            return "🟡"
        return "➖"
    disp["台本"] = disp.apply(lambda r: _sub_icon(r.get("台本提出日"), r.get("台本提出期限")), axis=1)
    disp["動画"] = disp.apply(lambda r: _sub_icon(r.get("動画提出日"), r.get("動画提出期限")), axis=1)

    show_cols = {
        "管理番号": "No.",
        "案件名":   "案件名",
        "ステータス表示": "ステータス",
        "担当台本作家": "台本作家",
        "担当編集者":  "編集者",
        "台本": "台本",
        "動画": "動画",
        "納期表示": "納期",
        "残り日数": "残り",
    }
    render_df = disp[[c for c in show_cols if c in disp.columns]].rename(columns=show_cols)

    def _row_style(row):
        raw_status = row.get("ステータス", "")
        status = next((s for s in STATUS_BG if s in raw_status), "")
        if status == "納品完了":
            return ["color:#94a3b8; font-style:italic"] * len(row)
        bg = STATUS_BG.get(status, "")
        return ["background-color:" + bg] * len(row)

    styled = render_df.style.apply(_row_style, axis=1)

    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=min(48 * len(render_df) + 48, 600),
        on_select="rerun",
        selection_mode="single-row",
        key=key + "_df",
    )

    selected_rows = event.selection.rows
    if selected_rows:
        return paged.iloc[[selected_rows[0]]]
    return pd.DataFrame()


# ─── プレミアム案件カード ──────────────────────────────────────────────────────

def render_project_cards(df: pd.DataFrame, selected_id: Optional[str]) -> Optional[str]:
    """
    プレミアム案件カードを描画。
    - ステータスカラーストライプ
    - 期限カウントダウンバッジ
    - 台本/動画 提出状況ミニバッジ
    """
    if df.empty:
        st.info("担当案件がありません。")
        return selected_id

    today = pd.Timestamp(date.today())

    for _, row in df.iterrows():
        status  = str(row.get("ステータス", ""))
        title   = str(row.get("案件名", "案件名なし"))
        mgmt_no = str(row.get("管理番号", "") or "")
        due     = row.get("納期")
        row_id  = str(row.get("ID", ""))
        writer  = str(row.get("担当台本作家", "") or "—")
        editor  = str(row.get("担当編集者", "") or "—")

        s_color  = STATUS_TEXT_COLOR.get(status, "#6b7280")
        s_bg     = STATUS_BG.get(status, "#f3f4f6")
        s_emoji  = STATUS_EMOJI.get(status, "")

        dl_pill    = _deadline_pill(due, today)
        script_b   = _mini_sub_badge("台本", row.get("台本提出日"), row.get("台本提出期限"), today)
        video_b    = _mini_sub_badge("動画", row.get("動画提出日"), row.get("動画提出期限"), today)

        is_sel     = (row_id == selected_id)
        card_extra = " selected" if is_sel else ""
        card_bg    = "#f0f7ff" if is_sel else "white"
        border_clr = "#3b82f6" if is_sel else s_color

        no_span = (
            '<span style="color:#94a3b8;font-size:0.85em;font-weight:600;">[' + mgmt_no + ']</span> '
            if mgmt_no else ""
        )

        st.markdown(
            '<div class="proj-card' + card_extra + '" style="background:' + card_bg + ';border-left-color:' + border_clr + ';">'
            '<div class="proj-card-stripe" style="background:' + border_clr + ';"></div>'
            '<div class="proj-card-inner">'

            # Top row: status badge + deadline pill
            '<div class="proj-card-top">'
            '<span style="background:' + s_bg + ';color:' + s_color + ';'
            'padding:2px 9px;border-radius:999px;font-size:0.76em;font-weight:700;">'
            + s_emoji + ' ' + status + '</span>'
            + dl_pill +
            '</div>'

            # Title
            '<div class="proj-card-title">' + no_span + title + '</div>'

            # Assignees
            '<div class="proj-card-meta">'
            '<span>✏️ ' + writer + '</span>'
            '<span>🎬 ' + editor + '</span>'
            '</div>'

            # Submission badges
            '<div class="proj-card-subs">' + script_b + video_b + '</div>'

            '</div></div>',
            unsafe_allow_html=True,
        )

        btn_label = "✅ 選択中" if is_sel else "この案件を更新 →"
        if st.button(btn_label, key="card_" + row_id, use_container_width=True,
                     type="primary" if is_sel else "secondary"):
            selected_id = row_id

    return selected_id


# ─── プレミアムリールカード ────────────────────────────────────────────────────

def render_reel_cards(df: pd.DataFrame, selected_id: Optional[str]) -> Optional[str]:
    if df.empty:
        st.info("担当リールがありません。")
        return selected_id

    today = pd.Timestamp(date.today())

    for _, row in df.iterrows():
        status   = str(row.get("ステータス", ""))
        title    = str(row.get("タイトル", "タイトルなし"))
        mgmt_no  = str(row.get("管理番号", "") or "")
        platform = str(row.get("プラットフォーム", "") or "")
        due      = row.get("投稿予定日")
        row_id   = str(row.get("ID", ""))
        writer   = str(row.get("担当台本作家", "") or "—")

        s_color  = REEL_STATUS_TEXT.get(status, "#6b7280")
        s_bg     = REEL_STATUS_BG.get(status, "#f3f4f6")
        s_emoji  = REEL_STATUS_EMOJI.get(status, "")
        dl_pill  = _deadline_pill(due, today)
        plat_b   = platform_badge_html(platform) if platform else ""

        is_sel    = (row_id == selected_id)
        card_extra = " selected" if is_sel else ""
        card_bg   = "#fdf4ff" if is_sel else "white"
        border_clr = "#a855f7" if is_sel else s_color

        no_span = (
            '<span style="color:#94a3b8;font-size:0.85em;font-weight:600;">[' + mgmt_no + ']</span> '
            if mgmt_no else ""
        )

        st.markdown(
            '<div class="proj-card' + card_extra + '" style="background:' + card_bg + ';border-left-color:' + border_clr + ';">'
            '<div class="proj-card-stripe" style="background:' + border_clr + ';"></div>'
            '<div class="proj-card-inner">'

            '<div class="proj-card-top">'
            '<span style="background:' + s_bg + ';color:' + s_color + ';'
            'padding:2px 9px;border-radius:999px;font-size:0.76em;font-weight:700;">'
            + s_emoji + ' ' + status + '</span>'
            + dl_pill +
            '</div>'

            '<div class="proj-card-title">' + no_span + title + '</div>'

            '<div class="proj-card-meta">'
            '<span>✏️ ' + writer + '</span>'
            '</div>'

            '<div class="proj-card-subs">' + plat_b + '</div>'

            '</div></div>',
            unsafe_allow_html=True,
        )

        btn_label = "✅ 選択中" if is_sel else "このリールを更新 →"
        if st.button(btn_label, key="reel_card_" + row_id, use_container_width=True,
                     type="primary" if is_sel else "secondary"):
            selected_id = row_id

    return selected_id


# ─── カレンダー HTML ──────────────────────────────────────────────────────────

def build_calendar_html(year: int, month: int, events: List[Dict]) -> str:
    events_by_date: Dict = defaultdict(list)
    for ev in events:
        events_by_date[ev["date"]].append(ev)

    month_cal  = _cal_module.monthcalendar(year, month)
    today      = date.today()
    day_names  = ["月", "火", "水", "木", "金", "土", "日"]

    html = '<div class="cal-wrap"><div class="cal-grid">'

    for i, dn in enumerate(day_names):
        cls = "sat" if i == 5 else ("sun" if i == 6 else "")
        html += '<div class="cal-hdr ' + cls + '">' + dn + '</div>'

    for week in month_cal:
        for i, day in enumerate(week):
            if day == 0:
                html += '<div class="cal-cell empty"></div>'
                continue

            day_date = date(year, month, day)
            cell_cls = "cal-cell"
            if i == 5:
                cell_cls += " sat"
            elif i == 6:
                cell_cls += " sun"
            if day_date == today:
                cell_cls += " today"
            elif day_date < today:
                cell_cls += " past"

            dn_cls = "cal-dn today-circle" if day_date == today else "cal-dn"
            html += '<div class="' + cell_cls + '"><span class="' + dn_cls + '">' + str(day) + '</span><br>'

            day_events = events_by_date.get(day_date, [])
            for ev in day_events[:3]:
                icon  = ev.get("icon", "")
                label = ev["title"]
                label = label[:11] + "…" if len(label) > 11 else label
                ev_cls = ev.get("css_class", "reel-sched")
                html += '<span class="cal-ev ' + ev_cls + '">' + icon + ' ' + label + '</span>'

            if len(day_events) > 3:
                html += '<span class="cal-ev-more">+' + str(len(day_events) - 3) + '件</span>'

            html += '</div>'

    html += '</div></div>'
    return html
