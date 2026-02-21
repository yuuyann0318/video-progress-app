"""
動画制作 × SNS投稿 管理システム — ライブコマンドセンター

■ 設計方針
  - ファーストビューで全体ヘルスが一目でわかる
  - 緊急案件・今週締切を最上部にアラート表示
  - パイプラインバーで進捗分布を視覚化
  - ロールカードにライブ件数を埋め込む
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from utils.ui import inject_css, render_pipeline_bar, GLOBAL_CSS
from utils.sheets import ensure_headers, load_data

st.set_page_config(
    page_title="制作管理システム",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# 起動時にスプレッドシートのヘッダーを確認・修復
with st.spinner("スプレッドシートを確認中..."):
    ensure_headers()


# ─── データ取得 ────────────────────────────────────────────────────────────────

try:
    from utils.reels import load_reels
    df_proj  = load_data()
    df_reels = load_reels()
except Exception:
    df_proj  = pd.DataFrame()
    df_reels = pd.DataFrame()

today      = pd.Timestamp(date.today())
week_end   = today + pd.Timedelta(days=7)


# ─── ヘルス計算 ────────────────────────────────────────────────────────────────

total_proj   = len(df_proj)
done_proj    = len(df_proj[df_proj["ステータス"] == "納品完了"]) if not df_proj.empty else 0
active_proj  = total_proj - done_proj

total_reels  = (
    len(df_reels[df_reels["ステータス"] != "アーカイブ"])
    if not df_reels.empty and "ステータス" in df_reels.columns else 0
)

proj_overdue = (
    len(df_proj[
        (df_proj["納期"].notna()) &
        (df_proj["納期"] < today) &
        (df_proj["ステータス"] != "納品完了")
    ])
    if not df_proj.empty else 0
)

proj_due_soon = (
    len(df_proj[
        (df_proj["納期"].notna()) &
        (df_proj["納期"] >= today) &
        (df_proj["納期"] <= week_end) &
        (df_proj["ステータス"] != "納品完了")
    ])
    if not df_proj.empty else 0
)

script_overdue = (
    len(df_proj[
        (df_proj["台本提出期限"].notna()) &
        (df_proj["台本提出日"].isna()) &
        (df_proj["台本提出期限"] < today)
    ])
    if not df_proj.empty and "台本提出期限" in df_proj.columns else 0
)

video_overdue = (
    len(df_proj[
        (df_proj["動画提出期限"].notna()) &
        (df_proj["動画提出日"].isna()) &
        (df_proj["動画提出期限"] < today)
    ])
    if not df_proj.empty and "動画提出期限" in df_proj.columns else 0
)

reel_this_week = (
    len(df_reels[
        (df_reels["投稿予定日"].notna()) &
        (df_reels["投稿予定日"] >= today) &
        (df_reels["投稿予定日"] <= week_end) &
        (df_reels["ステータス"] != "アーカイブ")
    ])
    if not df_reels.empty and "投稿予定日" in df_reels.columns else 0
)

# ヘルスステータス判定
health_level = "green"
if proj_overdue > 0 or script_overdue > 0 or video_overdue > 0:
    health_level = "red"
elif proj_due_soon > 0:
    health_level = "yellow"

health_icon  = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[health_level]
health_label = {"green": "正常", "yellow": "注意あり", "red": "要対応あり"}[health_level]
health_bg    = {"green": "#d1fae5", "yellow": "#fef9c3", "red": "#fee2e2"}[health_level]
health_color = {"green": "#065f46", "yellow": "#92400e", "red": "#991b1b"}[health_level]


# ─── ヒーローセクション ────────────────────────────────────────────────────────

today_str = date.today().strftime("%Y年%-m月%-d日")

st.markdown(
    '<div style="'
    'background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 40%, #0f172a 100%);'
    'border-radius: 20px; padding: 32px 40px; margin-bottom: 24px;'
    'position: relative; overflow: hidden;'
    '">'
    # 装飾リング
    '<div style="position:absolute;top:-40px;right:-40px;width:220px;height:220px;'
    'border-radius:50%;border:30px solid rgba(255,255,255,0.03);pointer-events:none;"></div>'
    '<div style="position:absolute;bottom:-60px;left:-20px;width:180px;height:180px;'
    'border-radius:50%;border:25px solid rgba(255,255,255,0.03);pointer-events:none;"></div>'
    # コンテンツ
    '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;">'
    '<div>'
    '<div style="color:rgba(255,255,255,0.5);font-size:0.82em;letter-spacing:0.12em;'
    'text-transform:uppercase;margin-bottom:6px;">Production Management System</div>'
    '<h1 style="color:white;font-size:1.9em;font-weight:900;margin:0 0 6px;letter-spacing:-0.02em;">'
    '🎬 動画制作 × SNS投稿 管理システム'
    '</h1>'
    '<div style="color:rgba(255,255,255,0.6);font-size:0.88em;">'
    + today_str + '　|　コマンドセンター'
    '</div>'
    '</div>'
    '<div style="background:' + health_bg + ';color:' + health_color + ';'
    'padding:10px 22px;border-radius:12px;font-weight:800;font-size:1em;">'
    + health_icon + ' システム ' + health_label +
    '</div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


# ─── KPIバー ──────────────────────────────────────────────────────────────────

kpi_items = [
    ("📁", str(total_proj),   "総案件数",     "#3b82f6", "#eff6ff"),
    ("🔄", str(active_proj),  "進行中",       "#8b5cf6", "#f5f3ff"),
    ("✅", str(done_proj),    "納品完了",     "#10b981", "#d1fae5"),
    ("🔴", str(proj_overdue), "期限超過",     "#ef4444", "#fee2e2"),
    ("🟡", str(proj_due_soon),"今週締切",     "#f59e0b", "#fffbeb"),
    ("📱", str(reel_this_week),"今週投稿予定", "#e1306c", "#fce7f3"),
]

cols = st.columns(len(kpi_items))
for col, (icon, val, label, color, bg) in zip(cols, kpi_items):
    col.markdown(
        '<div class="kpi-card" style="border-top:3px solid ' + color + ';background:' + bg + ';">'
        '<div class="kpi-value" style="color:' + color + ';">' + val + '</div>'
        '<div class="kpi-label">' + icon + ' ' + label + '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)


# ─── パイプライン分布バー ──────────────────────────────────────────────────────

if not df_proj.empty:
    st.markdown(
        '<div class="section-title">📊 パイプライン分布</div>',
        unsafe_allow_html=True,
    )
    render_pipeline_bar(df_proj)
    st.markdown("<br>", unsafe_allow_html=True)


# ─── 緊急アラートセクション ────────────────────────────────────────────────────

alerts = []

if proj_overdue > 0 and not df_proj.empty:
    overdue_df = df_proj[
        (df_proj["納期"].notna()) &
        (df_proj["納期"] < today) &
        (df_proj["ステータス"] != "納品完了")
    ]
    for _, r in overdue_df.head(3).iterrows():
        days_past = int((today - r["納期"]).days)
        alerts.append({
            "level": "red",
            "icon": "🔴",
            "title": str(r.get("案件名", "")) + "　― 納期 " + str(days_past) + "日超過",
            "sub": "担当: " + str(r.get("担当台本作家", "—")) + " / " + str(r.get("担当編集者", "—")),
            "page": "pages/1_📊_管理者.py",
        })

if script_overdue > 0 and not df_proj.empty:
    alerts.append({
        "level": "red",
        "icon": "✏️",
        "title": "台本提出期限超過 " + str(script_overdue) + " 件",
        "sub": "提出管理ページで詳細を確認",
        "page": "pages/6_📋_提出管理.py",
    })

if video_overdue > 0 and not df_proj.empty:
    alerts.append({
        "level": "red",
        "icon": "🎬",
        "title": "動画提出期限超過 " + str(video_overdue) + " 件",
        "sub": "提出管理ページで詳細を確認",
        "page": "pages/6_📋_提出管理.py",
    })

if proj_due_soon > 0 and not df_proj.empty:
    soon_df = df_proj[
        (df_proj["納期"].notna()) &
        (df_proj["納期"] >= today) &
        (df_proj["納期"] <= week_end) &
        (df_proj["ステータス"] != "納品完了")
    ]
    for _, r in soon_df.head(2).iterrows():
        delta = int((r["納期"] - today).days)
        label = "本日締切" if delta == 0 else "あと " + str(delta) + " 日"
        alerts.append({
            "level": "yellow",
            "icon": "🟡",
            "title": str(r.get("案件名", "")) + "　― " + label,
            "sub": "担当: " + str(r.get("担当台本作家", "—")) + " / " + str(r.get("担当編集者", "—")),
            "page": "pages/1_📊_管理者.py",
        })

if alerts:
    st.markdown(
        '<div class="section-title">⚡ 緊急・要対応アイテム</div>',
        unsafe_allow_html=True,
    )
    alert_bgs    = {"red": "#fff1f2", "yellow": "#fffbeb"}
    alert_colors = {"red": "#991b1b", "yellow": "#92400e"}
    alert_borders = {"red": "#ef4444", "yellow": "#f59e0b"}

    for a in alerts:
        lvl = a["level"]
        st.markdown(
            '<div class="alert-card" style="'
            'background:' + alert_bgs.get(lvl, "#f9fafb") + ';'
            'border-left-color:' + alert_borders.get(lvl, "#6b7280") + ';">'
            '<div class="alert-icon">' + a["icon"] + '</div>'
            '<div class="alert-body">'
            '<div class="alert-title" style="color:' + alert_colors.get(lvl, "#374151") + ';">' + a["title"] + '</div>'
            '<div class="alert-sub">' + a["sub"] + '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    st.markdown("<br>", unsafe_allow_html=True)
elif total_proj > 0:
    st.markdown(
        '<div style="background:#d1fae5;border-left:4px solid #10b981;'
        'padding:12px 20px;border-radius:0 10px 10px 0;margin-bottom:20px;'
        'color:#065f46;font-weight:600;">'
        '✅ 緊急案件なし — 全案件が順調に進行しています！'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)


# ─── ロール選択カード（上段3つ）───────────────────────────────────────────────

st.markdown(
    '<div class="section-title">🚀 ロールを選択</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3, gap="large")

# 管理者カード用ライブ数値
admin_badge = (
    ('<span style="background:#ef4444;color:white;border-radius:999px;'
     'padding:1px 8px;font-size:0.8em;font-weight:700;margin-left:6px;">'
     + str(proj_overdue) + ' 超過</span>')
    if proj_overdue > 0 else ""
)

with col1:
    st.markdown(
        '<div style="'
        'background: linear-gradient(135deg, #1e3a5f 0%, #2d5a9e 100%);'
        'border-radius: 16px; padding: 28px 24px; text-align: center;'
        'box-shadow: 0 4px 24px rgba(30,58,95,0.35); min-height: 200px;'
        'position:relative; overflow:hidden;">'
        '<div style="position:absolute;top:-20px;right:-20px;width:100px;height:100px;'
        'border-radius:50%;background:rgba(255,255,255,0.06);"></div>'
        '<div style="font-size:3em;margin-bottom:8px;">👑</div>'
        '<h2 style="color:white; margin:0 0 6px; font-size:1.3em; font-weight:800;">'
        '管理者' + admin_badge + '</h2>'
        '<p style="color:#93c5fd; font-size:0.85em; line-height:1.7; margin:0;">'
        '全案件の登録・進捗管理<br>'
        '担当者アサイン・KPI監視<br>'
        'リサーチ評価・案件化'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_📊_管理者.py", label="👑 管理者ページへ →", use_container_width=True)

# 台本作成者カード用ライブ数値
writer_projects = (
    len(df_proj[df_proj["ステータス"].isin(["台本作成中", "台本待ち"])])
    if not df_proj.empty else 0
)

with col2:
    st.markdown(
        '<div style="'
        'background: linear-gradient(135deg, #14532d 0%, #166534 100%);'
        'border-radius: 16px; padding: 28px 24px; text-align: center;'
        'box-shadow: 0 4px 24px rgba(20,83,45,0.35); min-height: 200px;'
        'position:relative; overflow:hidden;">'
        '<div style="position:absolute;top:-20px;right:-20px;width:100px;height:100px;'
        'border-radius:50%;background:rgba(255,255,255,0.06);"></div>'
        '<div style="font-size:3em;margin-bottom:8px;">✏️</div>'
        '<h2 style="color:white; margin:0 0 6px; font-size:1.3em; font-weight:800;">台本作成者</h2>'
        '<p style="color:#86efac; font-size:0.85em; line-height:1.7; margin:0;">'
        '台本URLの提出・新規案件登録<br>'
        'リール台本・キャプション作成<br>'
        'リサーチ提出'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_✏️_台本作成者.py", label="✏️ 台本作成者ページへ →", use_container_width=True)

# 動画編集者カード
with col3:
    st.markdown(
        '<div style="'
        'background: linear-gradient(135deg, #581c87 0%, #7e22ce 100%);'
        'border-radius: 16px; padding: 28px 24px; text-align: center;'
        'box-shadow: 0 4px 24px rgba(88,28,135,0.35); min-height: 200px;'
        'position:relative; overflow:hidden;">'
        '<div style="position:absolute;top:-20px;right:-20px;width:100px;height:100px;'
        'border-radius:50%;background:rgba(255,255,255,0.06);"></div>'
        '<div style="font-size:3em;margin-bottom:8px;">🎞️</div>'
        '<h2 style="color:white; margin:0 0 6px; font-size:1.3em; font-weight:800;">動画編集者</h2>'
        '<p style="color:#d8b4fe; font-size:0.85em; line-height:1.7; margin:0;">'
        '素材・完パケURLの提出<br>'
        'リール編集・納品完了更新<br>'
        '進捗ステータス管理'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_🎞️_動画編集者.py", label="🎞️ 動画編集者ページへ →", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─── サブカード（下段3つ）───────────────────────────────────────────────────────

col4, col5, col6 = st.columns(3, gap="large")

with col4:
    reel_count_str = str(total_reels) + " 件" if total_reels > 0 else ""
    st.markdown(
        '<div style="'
        'background: linear-gradient(135deg, #7f1d1d 0%, #be123c 100%);'
        'border-radius: 16px; padding: 24px 22px; text-align: center;'
        'box-shadow: 0 4px 20px rgba(127,29,29,0.3); min-height: 170px;">'
        '<div style="font-size:2.6em;margin-bottom:6px;">📱</div>'
        '<h2 style="color:white; margin:0 0 4px; font-size:1.2em; font-weight:800;">リール管理</h2>'
        '<div style="color:#fca5a5;font-size:0.82em;margin-bottom:6px;">' + reel_count_str + '</div>'
        '<p style="color:#fca5a5; font-size:0.82em; line-height:1.6; margin:0;">'
        'インスタリール / SNS投稿の全管理<br>'
        '制作パイプライン・パフォーマンス分析'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/4_📱_リール管理.py", label="📱 リール管理ページへ →", use_container_width=True)

with col5:
    week_str = ("今週 " + str(reel_this_week) + " 件投稿予定") if reel_this_week > 0 else ""
    st.markdown(
        '<div style="'
        'background: linear-gradient(135deg, #0c4a6e 0%, #0369a1 100%);'
        'border-radius: 16px; padding: 24px 22px; text-align: center;'
        'box-shadow: 0 4px 20px rgba(12,74,110,0.3); min-height: 170px;">'
        '<div style="font-size:2.6em;margin-bottom:6px;">📅</div>'
        '<h2 style="color:white; margin:0 0 4px; font-size:1.2em; font-weight:800;">投稿カレンダー</h2>'
        '<div style="color:#7dd3fc;font-size:0.82em;margin-bottom:6px;">' + week_str + '</div>'
        '<p style="color:#7dd3fc; font-size:0.82em; line-height:1.6; margin:0;">'
        '月別カレンダービュー<br>'
        '投稿予定 & 制作納期を一覧表示'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/5_📅_カレンダー.py", label="📅 カレンダーページへ →", use_container_width=True)

sub_alert_str = ""
if script_overdue + video_overdue > 0:
    sub_alert_str = (
        '<span style="background:#ef4444;color:white;border-radius:999px;'
        'padding:1px 8px;font-size:0.78em;font-weight:700;margin-left:4px;">'
        + str(script_overdue + video_overdue) + ' 超過</span>'
    )

with col6:
    st.markdown(
        '<div style="'
        'background: linear-gradient(135deg, #064e3b 0%, #059669 100%);'
        'border-radius: 16px; padding: 24px 22px; text-align: center;'
        'box-shadow: 0 4px 20px rgba(6,78,59,0.3); min-height: 170px;">'
        '<div style="font-size:2.6em;margin-bottom:6px;">📋</div>'
        '<h2 style="color:white; margin:0 0 4px; font-size:1.2em; font-weight:800;">'
        '提出管理' + sub_alert_str + '</h2>'
        '<p style="color:#a7f3d0; font-size:0.82em; line-height:1.6; margin:0;">'
        '台本・動画の提出期限を一元管理<br>'
        '担当者別スコアカード & 提出率'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/6_📋_提出管理.py", label="📋 提出管理ページへ →", use_container_width=True)


# ─── フッター ─────────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<hr style="border-color:#e2e8f0;">'
    '<div style="text-align:center;color:#94a3b8;font-size:0.8em;padding:6px 0;">'
    '動画制作 × SNS投稿 管理システム　|　Powered by Streamlit × Google Sheets'
    '</div>',
    unsafe_allow_html=True,
)
