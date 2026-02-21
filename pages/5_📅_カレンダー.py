"""
投稿カレンダー & スケジュール管理

月別カレンダービューに以下のイベントを表示:
  📱 インスタリール投稿予定
  ✅ 投稿済み
  🔴 動画案件 期限超過
  🟡 動画案件 今週締切
  🟢 動画案件 納期

アジェンダビュー（週次・月次リスト）も提供。
"""

import warnings
warnings.filterwarnings("ignore")

import calendar as _cal
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import List, Dict

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.sheets import load_data, clear_cache
from utils.reels import load_reels, clear_reel_cache
from utils.config import (
    STATUS_EMOJI, STATUS_BG,
    REEL_STATUS_EMOJI, REEL_STATUS_BG, REEL_STATUS_TEXT,
    PLATFORM_EMOJI, PLATFORM_COLOR,
)
from utils.ui import inject_css, build_calendar_html, days_label, reel_status_badge_html

# ─── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="投稿カレンダー | 動画制作管理",
    page_icon="📅",
    layout="wide",
)
inject_css()

# ─── セッション初期化（月ナビ用）─────────────────────────────────────────────

today = date.today()
if "cal_year"  not in st.session_state: st.session_state["cal_year"]  = today.year
if "cal_month" not in st.session_state: st.session_state["cal_month"] = today.month

# ─── サイドバー ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📅 カレンダー設定")
    st.markdown("---")

    st.markdown("### 📋 表示設定")
    show_reels     = st.checkbox("📱 リール投稿予定を表示",  value=True)
    show_deadlines = st.checkbox("⏰ 動画案件 納期を表示",   value=True)
    show_posted    = st.checkbox("✅ 投稿済みを表示",        value=False)
    show_archived  = st.checkbox("📦 アーカイブを非表示",    value=True)

    st.markdown("---")
    st.markdown("### 🔍 プラットフォームフィルター")

    from utils.config import PLATFORMS
    platform_show = st.multiselect(
        "表示するプラットフォーム",
        PLATFORMS,
        default=PLATFORMS,
        format_func=lambda p: f"{PLATFORM_EMOJI.get(p,'')} {p}",
    )

    st.markdown("---")
    if st.button("🔄 データを最新化", use_container_width=True):
        clear_cache()
        clear_reel_cache()
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="color:#94a3b8; font-size:0.78em; line-height:1.9;">
    <b>📅 カレンダーの見方</b><br>
    <span style="color:#e1306c;">■</span> リール投稿予定<br>
    <span style="color:#10b981;">■</span> 投稿済み<br>
    <span style="color:#ef4444;">■</span> 期限超過（納期）<br>
    <span style="color:#f59e0b;">■</span> 今週締切（納期）<br>
    <span style="color:#10b981;">■</span> 通常納期<br>
    </div>
    """, unsafe_allow_html=True)


# ─── データ取得 ────────────────────────────────────────────────────────────────

df_projects = load_data()
df_reels    = load_reels()

# ─── イベント構築 ─────────────────────────────────────────────────────────────

def build_events() -> List[Dict]:
    events = []
    now = date.today()

    # ── リール投稿予定 ──────────────────────────────────────────────────────
    if show_reels and not df_reels.empty:
        df_r = df_reels.copy()
        if show_archived:
            df_r = df_r[df_r["ステータス"] != "アーカイブ"]
        if platform_show:
            df_r = df_r[df_r["プラットフォーム"].isin(platform_show)]

        for _, row in df_r.iterrows():
            sched_date = row.get("投稿予定日")
            status     = str(row.get("ステータス", ""))
            if pd.isna(sched_date):
                continue

            ev_date = sched_date.date() if hasattr(sched_date, "date") else sched_date
            if status == "投稿済み":
                if not show_posted:
                    continue
                css = "reel-posted"
                icon = "✅"
            else:
                css = "reel-sched"
                icon = PLATFORM_EMOJI.get(str(row.get("プラットフォーム", "")), "📱")

            events.append({
                "date":      ev_date,
                "title":     str(row.get("タイトル", "—")),
                "css_class": css,
                "icon":      icon,
                "type":      "reel",
                "data":      row.to_dict(),
            })

    # ── 動画案件 納期 ───────────────────────────────────────────────────────
    if show_deadlines and not df_projects.empty:
        df_p = df_projects[df_projects["ステータス"] != "納品完了"].copy()
        for _, row in df_p.iterrows():
            due = row.get("納期")
            if pd.isna(due):
                continue
            due_date = due.date() if hasattr(due, "date") else due
            delta = (due_date - now).days
            if delta < 0:
                css = "deadline-over"
                icon = "🔴"
            elif delta <= 7:
                css = "deadline-soon"
                icon = "🟡"
            else:
                css = "deadline-ok"
                icon = "🟢"
            events.append({
                "date":      due_date,
                "title":     str(row.get("案件名", "—")),
                "css_class": css,
                "icon":      icon,
                "type":      "deadline",
                "data":      row.to_dict(),
            })

    return events


all_events = build_events()

# ─── メインコンテンツ ──────────────────────────────────────────────────────────

st.markdown("## 📅 投稿カレンダー & スケジュール管理")

# ── 月ナビゲーション ──────────────────────────────────────────────────────────

nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 3, 1, 1])
with nav1:
    if st.button("◀◀ 前年", use_container_width=True):
        st.session_state["cal_year"] -= 1
        st.rerun()
with nav2:
    if st.button("◀ 前月", use_container_width=True):
        if st.session_state["cal_month"] == 1:
            st.session_state["cal_year"]  -= 1
            st.session_state["cal_month"]  = 12
        else:
            st.session_state["cal_month"] -= 1
        st.rerun()
with nav3:
    month_names = ["", "1月", "2月", "3月", "4月", "5月", "6月",
                   "7月", "8月", "9月", "10月", "11月", "12月"]
    y = st.session_state["cal_year"]
    m = st.session_state["cal_month"]
    st.markdown(
        f'<div style="text-align:center;font-size:1.5em;font-weight:800;padding:6px 0;">'
        f'📅 {y}年 {month_names[m]}</div>',
        unsafe_allow_html=True,
    )
with nav4:
    if st.button("次月 ▶", use_container_width=True):
        if st.session_state["cal_month"] == 12:
            st.session_state["cal_year"]  += 1
            st.session_state["cal_month"]  = 1
        else:
            st.session_state["cal_month"] += 1
        st.rerun()
with nav5:
    if st.button("次年 ▶▶", use_container_width=True):
        st.session_state["cal_year"] += 1
        st.rerun()

# 今月に戻るボタン
if (y, m) != (today.year, today.month):
    if st.button("📍 今月に戻る", use_container_width=True):
        st.session_state["cal_year"]  = today.year
        st.session_state["cal_month"] = today.month
        st.rerun()

# ── カレンダー描画 ─────────────────────────────────────────────────────────

month_events = [ev for ev in all_events
                if ev["date"].year == y and ev["date"].month == m]

cal_html = build_calendar_html(y, m, month_events)
st.markdown(cal_html, unsafe_allow_html=True)

# ── 凡例 ─────────────────────────────────────────────────────────────────

st.markdown("""
<div style="display:flex;gap:16px;padding:12px 0;flex-wrap:wrap;font-size:0.82em;">
  <span><b style="color:#e1306c;">━</b> リール投稿予定</span>
  <span><b style="color:#10b981;">━</b> 投稿済み</span>
  <span><b style="color:#ef4444;">━</b> 期限超過（納期）</span>
  <span><b style="color:#f59e0b;">━</b> 今週締切（納期）</span>
  <span><b style="color:#10b981;">━</b> 通常納期</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── タブ：アジェンダ / 今週 / アラート ────────────────────────────────────

tab_agenda, tab_week, tab_alert = st.tabs([
    f"📋 今月のアジェンダ ({len(month_events)}件)",
    "📆 今週のスケジュール",
    "🚨 アラート & 確認事項",
])

# ── 今月アジェンダ ──────────────────────────────────────────────────────────

with tab_agenda:
    if not month_events:
        st.info("今月のイベントはありません。")
    else:
        # 日付でグループ化
        from collections import defaultdict
        events_by_date = defaultdict(list)
        for ev in sorted(month_events, key=lambda x: x["date"]):
            events_by_date[ev["date"]].append(ev)

        for ev_date in sorted(events_by_date.keys()):
            is_today = ev_date == today
            is_past  = ev_date < today
            date_color = "#3b82f6" if is_today else ("#94a3b8" if is_past else "#1e3a5f")
            weekday_jp = ["月", "火", "水", "木", "金", "土", "日"][ev_date.weekday()]
            wday_color = "#2563eb" if ev_date.weekday() == 5 else (
                "#dc2626" if ev_date.weekday() == 6 else date_color
            )
            today_badge = ' <span style="background:#3b82f6;color:white;padding:1px 8px;border-radius:999px;font-size:0.75em;">TODAY</span>' if is_today else ""

            st.markdown(
                f'<div style="font-weight:800;font-size:1em;color:{wday_color};'
                f'margin:16px 0 6px;">'
                f'📅 {ev_date.strftime("%m/%d")} ({weekday_jp}){today_badge}</div>',
                unsafe_allow_html=True,
            )

            for ev in events_by_date[ev_date]:
                ev_type = ev.get("type", "reel")
                data    = ev.get("data", {})

                if ev_type == "reel":
                    plat  = str(data.get("プラットフォーム", ""))
                    plat_c = PLATFORM_COLOR.get(plat, "#7c3aed")
                    plat_e = PLATFORM_EMOJI.get(plat, "📱")
                    status = str(data.get("ステータス", ""))
                    st_bg  = REEL_STATUS_BG.get(status, "#f3f4f6")
                    st_e   = REEL_STATUS_EMOJI.get(status, "")
                    title  = str(data.get("タイトル", "—"))
                    mgmt   = str(data.get("管理番号", ""))
                    post_t = str(data.get("投稿時間", ""))
                    writer = str(data.get("担当台本作家", ""))
                    editor = str(data.get("担当編集者", ""))
                    post_url = str(data.get("投稿URL", ""))

                    time_str = f" ⏰ {post_t}" if post_t else ""
                    url_str  = f' &nbsp; <a href="{post_url}" target="_blank">🔗 投稿を見る</a>' if post_url else ""
                    no_str   = f"[{mgmt}] " if mgmt else ""

                    st.markdown(
                        f'<div style="background:{st_bg};border-left:4px solid {plat_c};'
                        f'border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<b style="font-size:0.95em;">{plat_e} {no_str}{title}</b>'
                        f'<span style="background:{plat_c};color:white;padding:2px 8px;'
                        f'border-radius:999px;font-size:0.75em;">{plat}</span>'
                        f'</div>'
                        f'<div style="margin-top:5px;font-size:0.8em;color:#64748b;">'
                        f'{st_e} {status}{time_str}'
                        f'{"　台本作家: " + writer if writer else ""}'
                        f'{"　編集者: " + editor if editor else ""}'
                        f'{url_str}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                elif ev_type == "deadline":
                    status = str(data.get("ステータス", ""))
                    st_bg  = STATUS_BG.get(status, "#f3f4f6")
                    st_e   = STATUS_EMOJI.get(status, "")
                    title  = str(data.get("案件名", "—"))
                    mgmt   = str(data.get("管理番号", ""))
                    writer = str(data.get("担当台本作家", ""))
                    editor = str(data.get("担当編集者", ""))
                    icon   = ev.get("icon", "📅")
                    no_str = f"[{mgmt}] " if mgmt else ""

                    st.markdown(
                        f'<div style="background:{st_bg};border-left:4px solid #6b7280;'
                        f'border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px;">'
                        f'<div style="font-weight:700;font-size:0.9em;">'
                        f'{icon} 納期: {no_str}{title}</div>'
                        f'<div style="margin-top:4px;font-size:0.8em;color:#64748b;">'
                        f'{st_e} {status}'
                        f'{"　台本作家: " + writer if writer else ""}'
                        f'{"　編集者: " + editor if editor else ""}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

# ── 今週スケジュール ──────────────────────────────────────────────────────────

with tab_week:
    week_start = today - timedelta(days=today.weekday())  # 月曜日
    week_end   = week_start + timedelta(days=6)

    week_events = [ev for ev in all_events
                   if week_start <= ev["date"] <= week_end]

    st.markdown(
        f'### 📆 {week_start.strftime("%m/%d")} 〜 {week_end.strftime("%m/%d")} の予定'
    )

    if not week_events:
        st.success("✨ 今週の予定はありません！")
    else:
        from collections import defaultdict
        week_by_date = defaultdict(list)
        for ev in week_events:
            week_by_date[ev["date"]].append(ev)

        day_cols = st.columns(7)
        weekday_jp = ["月", "火", "水", "木", "金", "土", "日"]
        for i in range(7):
            d = week_start + timedelta(days=i)
            is_today = (d == today)
            header_bg = "#3b82f6" if is_today else ("#e2e8f0" if i < 5 else "#fee2e2" if i == 6 else "#dbeafe")
            header_color = "white" if is_today else "#374151"
            with day_cols[i]:
                st.markdown(
                    f'<div style="background:{header_bg};color:{header_color};'
                    f'border-radius:8px;padding:6px;text-align:center;font-weight:700;'
                    f'font-size:0.85em;margin-bottom:6px;">'
                    f'{weekday_jp[i]}<br>{d.strftime("%m/%d")}</div>',
                    unsafe_allow_html=True,
                )
                for ev in week_by_date.get(d, []):
                    ev_type = ev.get("type", "reel")
                    icon    = ev.get("icon", "📌")
                    title   = ev["title"][:10] + "…" if len(ev["title"]) > 10 else ev["title"]
                    css     = ev.get("css_class", "reel-sched")
                    bg_map  = {
                        "reel-sched":    "#fce7f3", "reel-posted":  "#d1fae5",
                        "deadline-over": "#fee2e2", "deadline-soon": "#fef9c3",
                        "deadline-ok":   "#d1fae5",
                    }
                    bg = bg_map.get(css, "#f3f4f6")
                    st.markdown(
                        f'<div style="background:{bg};border-radius:6px;'
                        f'padding:4px 6px;margin-bottom:4px;font-size:0.75em;">'
                        f'{icon} {title}</div>',
                        unsafe_allow_html=True,
                    )


# ── アラートタブ ─────────────────────────────────────────────────────────────

with tab_alert:
    st.markdown("### 🚨 要対応アラート")

    has_alert = False

    # 1. 今日投稿予定のリール
    today_reels = [ev for ev in all_events
                   if ev["type"] == "reel" and ev["date"] == today
                   and ev["data"].get("ステータス") == "投稿予定"]
    if today_reels:
        has_alert = True
        st.markdown(f"#### 📱 本日投稿予定 ({len(today_reels)}件) — 今すぐ投稿！")
        for ev in today_reels:
            data = ev["data"]
            plat = str(data.get("プラットフォーム", ""))
            plat_e = PLATFORM_EMOJI.get(plat, "📱")
            plat_c = PLATFORM_COLOR.get(plat, "#7c3aed")
            post_url = str(data.get("投稿URL", ""))
            title = str(data.get("タイトル", "—"))
            post_t = str(data.get("投稿時間", ""))
            final_url = str(data.get("完パケURL", ""))
            time_str   = "　⏰ " + post_t if post_t else ""
            final_link = '<a href="' + final_url + '" target="_blank">完パケを確認</a>　' if final_url else ""
            post_link  = '<a href="' + post_url + '" target="_blank">投稿URLを開く</a>' if post_url else ""
            final_part = "📹 " + final_link if final_url else ""
            post_part  = "🔗 " + post_link  if post_url  else ""
            st.markdown(
                f'<div style="background:#fce7f3;border:2px solid #e1306c;border-radius:12px;'
                f'padding:14px 18px;margin-bottom:8px;">'
                f'<b style="font-size:1em;">{plat_e} {title}</b>'
                f'{time_str}<br>'
                f'<div style="margin-top:6px;font-size:0.85em;">'
                f'{final_part}{post_part}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    # 2. 明日投稿予定のリール
    tomorrow = today + timedelta(days=1)
    tmr_reels = [ev for ev in all_events
                 if ev["type"] == "reel" and ev["date"] == tomorrow
                 and ev["data"].get("ステータス") in ["投稿予定", "レビュー中"]]
    if tmr_reels:
        has_alert = True
        st.markdown(f"#### ⚠️ 明日投稿予定 ({len(tmr_reels)}件) — 最終確認を！")
        for ev in tmr_reels:
            data = ev["data"]
            plat = str(data.get("プラットフォーム", ""))
            plat_e = PLATFORM_EMOJI.get(plat, "📱")
            status = str(data.get("ステータス", ""))
            st_e = REEL_STATUS_EMOJI.get(status, "")
            title = str(data.get("タイトル", "—"))
            st.markdown(
                f'<div style="background:#fef9c3;border-left:4px solid #f59e0b;'
                f'border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px;">'
                f'<b>{plat_e} {title}</b> &nbsp; {st_e} {status}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # 3. 期限超過した動画案件
    overdue_proj = [ev for ev in all_events
                    if ev["type"] == "deadline" and ev["css_class"] == "deadline-over"]
    if overdue_proj:
        has_alert = True
        st.markdown(f"#### 🔴 期限超過の案件 ({len(overdue_proj)}件) — 至急対応！")
        for ev in overdue_proj:
            data    = ev["data"]
            title   = str(data.get("案件名", "—"))
            status  = str(data.get("ステータス", ""))
            due_str = ev["date"].strftime("%m/%d")
            delta   = (today - ev["date"]).days
            writer  = str(data.get("担当台本作家", ""))
            editor  = str(data.get("担当編集者", ""))
            st.markdown(
                f'<div style="background:#fee2e2;border-left:4px solid #ef4444;'
                f'border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px;">'
                f'<b>🔴 {title}</b> &nbsp; <span style="color:#ef4444;font-weight:700;">'
                f'{delta}日超過</span> (納期: {due_str})<br>'
                f'<span style="font-size:0.82em;color:#64748b;">'
                f'{STATUS_EMOJI.get(status,"")} {status}'
                f'{"　台本作家: " + writer if writer else ""}'
                f'{"　編集者: " + editor if editor else ""}'
                f'</span></div>',
                unsafe_allow_html=True,
            )

    # 4. 3日以内に投稿予定だがステータスが「投稿予定」でないリール
    soon_reels = [ev for ev in all_events
                  if ev["type"] == "reel"
                  and today <= ev["date"] <= today + timedelta(days=3)
                  and ev["data"].get("ステータス") not in ["投稿予定", "投稿済み", "アーカイブ"]]
    if soon_reels:
        has_alert = True
        st.markdown(f"#### 🟡 3日以内に投稿予定（未完成） ({len(soon_reels)}件)")
        for ev in soon_reels:
            data = ev["data"]
            status = str(data.get("ステータス", ""))
            st_e = REEL_STATUS_EMOJI.get(status, "")
            plat_e = PLATFORM_EMOJI.get(str(data.get("プラットフォーム", "")), "📱")
            title = str(data.get("タイトル", "—"))
            due_str = ev["date"].strftime("%m/%d")
            st.markdown(
                f'<div style="background:#fef9c3;border-left:4px solid #f59e0b;'
                f'border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px;">'
                f'<b>{plat_e} {title}</b> &nbsp; 投稿予定: {due_str}<br>'
                f'<span style="font-size:0.82em;color:#64748b;">'
                f'現在のステータス: {st_e} {status}'
                f'</span></div>',
                unsafe_allow_html=True,
            )

    if not has_alert:
        st.success("""
        ✅ 現在、対応が必要なアラートはありません！

        すべての案件がスケジュール通りです。お疲れ様です！🎉
        """)

    # 5. 概要サマリー
    st.markdown("---")
    st.markdown("#### 📊 スケジュールサマリー")
    next_30_reels = [ev for ev in all_events
                     if ev["type"] == "reel"
                     and today <= ev["date"] <= today + timedelta(days=30)
                     and ev["data"].get("ステータス") != "アーカイブ"]
    upcoming_by_week = {}
    for ev in next_30_reels:
        week_num = (ev["date"] - today).days // 7
        week_label = f"今週" if week_num == 0 else f"{week_num+1}週目"
        upcoming_by_week[week_label] = upcoming_by_week.get(week_label, 0) + 1

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("📅 今後30日の投稿予定", len(next_30_reels))
    s2.metric("🔴 期限超過案件",       len(overdue_proj))
    s3.metric("📱 本日の投稿",         len(today_reels))
    s4.metric("⚠️ 3日以内（未完成）", len(soon_reels))
