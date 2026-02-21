"""
🎬 動画制作管理システム — ホーム（カンバンボード）

トップページ = カンバンボード。
全案件の進捗を一目で把握し、ステータスの全体像をつかむ。
"""

import pandas as pd
import streamlit as st
from datetime import date

from utils.sheets import clear_cache, ensure_headers, load_data
from utils.ui import inject_css, render_kanban_board, render_pipeline_bar

st.set_page_config(
    page_title="動画制作管理",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()
ensure_headers()

# ── データ取得 ───────────────────────────────────────────────────────────────
df = load_data()
today = pd.Timestamp(date.today())

# ── サイドバー ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 動画制作管理")
    st.markdown("---")
    st.markdown("### 🔍 フィルター")
    search    = st.text_input("検索", placeholder="案件名・担当者・管理番号")
    hide_done = st.checkbox("納品完了を非表示", value=True)
    st.markdown("---")
    if st.button("🔄 データ更新", use_container_width=True):
        clear_cache()
        st.rerun()

# ── フィルター適用 ────────────────────────────────────────────────────────────
filtered = df.copy()
if search:
    q = search.strip()
    mask = (
        filtered["案件名"].str.contains(q, na=False, case=False)
        | filtered["担当台本作家"].str.contains(q, na=False, case=False)
        | filtered["担当編集者"].str.contains(q, na=False, case=False)
        | filtered["管理番号"].str.contains(q, na=False, case=False)
    )
    filtered = filtered[mask]
if hide_done:
    filtered = filtered[filtered["ステータス"] != "納品完了"]

# ── KPIバー ──────────────────────────────────────────────────────────────────
total   = len(df)
active  = len(df[~df["ステータス"].isin(["納品完了", "未着手"])])
done    = len(df[df["ステータス"] == "納品完了"])
overdue = len(df[
    (df["納期"].notna()) & (df["納期"] < today) & (df["ステータス"] != "納品完了")
])
soon = len(df[
    (df["納期"].notna()) & (df["納期"] >= today)
    & (df["納期"] <= today + pd.Timedelta(days=7))
    & (df["ステータス"] != "納品完了")
])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📁 総案件数",  total)
c2.metric("⚡ 進行中",    active)
c3.metric("✅ 納品完了",  done)
c4.metric("🔴 期限超過",  overdue)
c5.metric("⏰ 今週締切",  soon)

# ── パイプラインバー ──────────────────────────────────────────────────────────
render_pipeline_bar(filtered)

# ── カンバンボード ────────────────────────────────────────────────────────────
label = f"（検索: {search}）" if search else ""
st.markdown(f"### 🗂️ 案件カンバン {label}")

if df.empty:
    st.info("案件がまだ登録されていません。「案件管理」ページから登録してください。")
else:
    render_kanban_board(filtered)
