"""
提出管理ダッシュボード

全担当者の台本・動画の提出状況を一元管理。
- 案件別ビュー: 全案件の台本/動画 提出期限・提出日・遅延状況を一覧
- 担当者別ビュー: 台本作家・編集者ごとのスコアカード
- KPI: 期限超過数・今日期限・今週提出予定・提出率
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date, timedelta

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.sheets import load_data, update_row, clear_cache
from utils.ui import inject_css, status_badge_html, days_label

# ─── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="提出管理 | 動画制作管理",
    page_icon="📋",
    layout="wide",
)
inject_css()

# ─── ユーティリティ ────────────────────────────────────────────────────────────

def _fmt_date(val) -> str:
    if pd.notna(val) and hasattr(val, "strftime"):
        return val.strftime("%Y/%m/%d")
    return "—"

def _submission_status(deadline, submitted_date, today) -> tuple:
    """
    Returns: (label, emoji, bg_color, text_color)
    """
    has_sub = pd.notna(submitted_date)
    has_dl  = pd.notna(deadline)

    if has_sub:
        # 提出済み → 期限内 or 遅延提出
        if has_dl and submitted_date > deadline:
            return ("遅延提出", "⚠️", "#fef9c3", "#92400e")
        return ("提出済み", "✅", "#d1fae5", "#065f46")
    if not has_dl:
        return ("期限未設定", "➖", "#f3f4f6", "#6b7280")
    if deadline < today:
        return ("期限超過", "🔴", "#fee2e2", "#991b1b")
    if deadline <= today + pd.Timedelta(days=3):
        return ("3日以内", "🟠", "#ffedd5", "#9a3412")
    return ("未提出", "🟡", "#fef9c3", "#92400e")

def _status_badge(label, emoji, bg, color) -> str:
    return (
        '<span style="background:' + bg + ';color:' + color + ';'
        'padding:3px 10px;border-radius:999px;font-size:0.8em;font-weight:700;">'
        + emoji + " " + label + "</span>"
    )

# ─── データ読み込み ────────────────────────────────────────────────────────────

today_ts = pd.Timestamp(date.today())

df_all = load_data()

# ─── サイドバー ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📋 提出管理")
    st.markdown("---")

    # 担当者フィルター
    st.markdown("### 🔍 担当者で絞り込み")
    all_writers = sorted([w for w in df_all["担当台本作家"].dropna().unique() if str(w).strip()])
    all_editors = sorted([e for e in df_all["担当編集者"].dropna().unique() if str(e).strip()])

    filter_writer = st.multiselect("台本作家", all_writers)
    filter_editor = st.multiselect("編集者",   all_editors)

    st.markdown("---")
    st.markdown("### 📋 表示フィルター")
    hide_done      = st.checkbox("✅ 納品完了を非表示", value=True)
    only_overdue   = st.checkbox("🔴 期限超過のみ表示", value=False)
    only_this_week = st.checkbox("📅 今週期限のみ表示", value=False)

    st.markdown("---")
    if st.button("🔄 データを最新化", use_container_width=True):
        clear_cache()
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="color:#94a3b8;font-size:0.8em;line-height:2;">
    <b>ステータス凡例</b><br>
    ✅ 提出済み<br>
    ⚠️ 遅延提出（期限後に提出）<br>
    🟡 未提出（期限内）<br>
    🟠 3日以内に期限<br>
    🔴 期限超過（未提出）<br>
    ➖ 期限未設定
    </div>
    """, unsafe_allow_html=True)

# ─── ヘッダー ─────────────────────────────────────────────────────────────────

st.markdown("## 📋 提出管理ダッシュボード")
st.caption("台本・動画の提出期限と実績を担当者ごとに一元管理")
st.markdown("---")

if df_all.empty:
    st.warning("案件がまだ登録されていません。")
    st.stop()

# ─── データ前処理 ─────────────────────────────────────────────────────────────

df = df_all.copy()

# 納品完了を非表示
if hide_done:
    df = df[df["ステータス"] != "納品完了"]

# 担当者フィルター
if filter_writer:
    df = df[df["担当台本作家"].isin(filter_writer)]
if filter_editor:
    df = df[df["担当編集者"].isin(filter_editor)]

# ─── KPIバー ─────────────────────────────────────────────────────────────────

df_kpi = df_all[df_all["ステータス"] != "納品完了"].copy()
week_end = today_ts + pd.Timedelta(days=7)

# 台本KPI
script_overdue = len(df_kpi[
    df_kpi["台本提出期限"].notna() &
    (df_kpi["台本提出期限"] < today_ts) &
    df_kpi["台本提出日"].isna()
])
script_this_week = len(df_kpi[
    df_kpi["台本提出期限"].notna() &
    (df_kpi["台本提出期限"] >= today_ts) &
    (df_kpi["台本提出期限"] <= week_end) &
    df_kpi["台本提出日"].isna()
])
script_done = len(df_kpi[df_kpi["台本提出日"].notna()])

# 動画KPI
video_overdue = len(df_kpi[
    df_kpi["動画提出期限"].notna() &
    (df_kpi["動画提出期限"] < today_ts) &
    df_kpi["動画提出日"].isna()
])
video_this_week = len(df_kpi[
    df_kpi["動画提出期限"].notna() &
    (df_kpi["動画提出期限"] >= today_ts) &
    (df_kpi["動画提出期限"] <= week_end) &
    df_kpi["動画提出日"].isna()
])
video_done = len(df_kpi[df_kpi["動画提出日"].notna()])

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("✏️ 台本 提出済み",    script_done)
k2.metric("🔴 台本 期限超過",    script_overdue,   delta=None)
k3.metric("📅 台本 今週期限",    script_this_week)
k4.metric("🎬 動画 提出済み",    video_done)
k5.metric("🔴 動画 期限超過",    video_overdue,    delta=None)
k6.metric("📅 動画 今週期限",    video_this_week)

st.markdown("---")

# ─── タブ ─────────────────────────────────────────────────────────────────────

tab_list, tab_person, tab_edit = st.tabs(["📊 案件別ビュー", "👤 担当者別ビュー", "✏️ 期限を一括設定"])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: 案件別ビュー
# ══════════════════════════════════════════════════════════════════════════════

with tab_list:
    st.markdown(f"### 📊 案件別 提出状況一覧　`{len(df)}` 件")

    if df.empty:
        st.info("表示できる案件がありません。")
    else:
        # 追加フィルター
        if only_overdue:
            mask = (
                (df["台本提出期限"].notna() & (df["台本提出期限"] < today_ts) & df["台本提出日"].isna()) |
                (df["動画提出期限"].notna() & (df["動画提出期限"] < today_ts) & df["動画提出日"].isna())
            )
            df = df[mask]
        if only_this_week:
            mask = (
                (df["台本提出期限"].notna() & (df["台本提出期限"] >= today_ts) & (df["台本提出期限"] <= week_end)) |
                (df["動画提出期限"].notna() & (df["動画提出期限"] >= today_ts) & (df["動画提出期限"] <= week_end))
            )
            df = df[mask]

        df = df.sort_values("台本提出期限", na_position="last").reset_index(drop=True)

        for _, row in df.iterrows():
            mgmt   = str(row.get("管理番号", "") or "")
            title  = str(row.get("案件名", "") or "無題")
            status = str(row.get("ステータス", ""))
            writer = str(row.get("担当台本作家", "") or "未定")
            editor = str(row.get("担当編集者", "") or "未定")

            s_dl  = row.get("台本提出期限")
            s_sub = row.get("台本提出日")
            v_dl  = row.get("動画提出期限")
            v_sub = row.get("動画提出日")

            s_label, s_emoji, s_bg, s_tc = _submission_status(s_dl, s_sub, today_ts)
            v_label, v_emoji, v_bg, v_tc = _submission_status(v_dl, v_sub, today_ts)

            # カード背景: 期限超過があれば薄赤
            overdue = (s_label == "期限超過") or (v_label == "期限超過")
            card_bg = "#fff5f5" if overdue else "#ffffff"

            label_no = ("[" + mgmt + "] ") if mgmt else ""

            with st.container():
                st.markdown(
                    '<div style="background:' + card_bg + ';border:1px solid #e2e8f0;'
                    'border-radius:12px;padding:14px 18px;margin-bottom:10px;">',
                    unsafe_allow_html=True,
                )

                row_top, row_badge = st.columns([4, 1])
                with row_top:
                    st.markdown(f"**{label_no}{title}**")
                with row_badge:
                    st.markdown(status_badge_html(status), unsafe_allow_html=True)

                c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 2, 2])
                with c1:
                    st.caption("✏️ 台本作家")
                    st.markdown(f"**{writer}**")
                with c2:
                    st.caption("台本提出期限 → 実績")
                    dl_str  = _fmt_date(s_dl)
                    sub_str = _fmt_date(s_sub)
                    st.markdown(
                        dl_str + " → " + sub_str + "&nbsp;&nbsp;" +
                        _status_badge(s_label, s_emoji, s_bg, s_tc),
                        unsafe_allow_html=True,
                    )
                with c3:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                with c4:
                    st.caption("🎬 編集者")
                    st.markdown(f"**{editor}**")
                with c5:
                    st.caption("動画提出期限 → 実績")
                    v_dl_str  = _fmt_date(v_dl)
                    v_sub_str = _fmt_date(v_sub)
                    st.markdown(
                        v_dl_str + " → " + v_sub_str + "&nbsp;&nbsp;" +
                        _status_badge(v_label, v_emoji, v_bg, v_tc),
                        unsafe_allow_html=True,
                    )

                st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: 担当者別ビュー
# ══════════════════════════════════════════════════════════════════════════════

with tab_person:

    def _person_scorecard(person_name: str, person_df: pd.DataFrame, role: str,
                          dl_col: str, sub_col: str) -> None:
        """担当者1人分のスコアカードを描画"""
        total = len(person_df)
        submitted  = person_df[sub_col].notna().sum()
        overdue_n  = len(person_df[
            person_df[dl_col].notna() &
            (person_df[dl_col] < today_ts) &
            person_df[sub_col].isna()
        ])
        this_week_n = len(person_df[
            person_df[dl_col].notna() &
            (person_df[dl_col] >= today_ts) &
            (person_df[dl_col] <= week_end) &
            person_df[sub_col].isna()
        ])

        rate = int(submitted / total * 100) if total > 0 else 0
        border_color = "#ef4444" if overdue_n > 0 else ("#f59e0b" if this_week_n > 0 else "#10b981")

        st.markdown(
            '<div style="border:2px solid ' + border_color + ';border-radius:14px;'
            'padding:16px 20px;margin-bottom:16px;">',
            unsafe_allow_html=True,
        )
        st.markdown(f"#### {role} **{person_name}**")

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("📁 担当案件", total)
        sc2.metric("✅ 提出済み", int(submitted))
        sc3.metric("🔴 期限超過", int(overdue_n))
        sc4.metric("📅 今週期限", int(this_week_n))

        # プログレスバー
        st.progress(rate / 100, text=f"提出率 {rate}%")

        # 案件リスト
        with st.expander("案件一覧を見る"):
            for _, r in person_df.sort_values(dl_col, na_position="last").iterrows():
                mgmt_n = str(r.get("管理番号", "") or "")
                ttl    = str(r.get("案件名", "") or "無題")
                label_n = ("[" + mgmt_n + "] ") if mgmt_n else ""
                lbl, emo, bg, tc = _submission_status(r.get(dl_col), r.get(sub_col), today_ts)
                dl_s  = _fmt_date(r.get(dl_col))
                sub_s = _fmt_date(r.get(sub_col))
                st.markdown(
                    "- **" + label_n + ttl + "**　期限: " + dl_s + "　実績: " + sub_s +
                    "　" + _status_badge(lbl, emo, bg, tc),
                    unsafe_allow_html=True,
                )

        st.markdown("</div>", unsafe_allow_html=True)

    # ── 台本作家セクション ───────────────────────────────────────────────────

    st.markdown("### ✏️ 台本作家 別 提出状況")

    df_active = df_all[df_all["ステータス"] != "納品完了"].copy()

    writers_found = sorted([w for w in df_active["担当台本作家"].dropna().unique() if str(w).strip()])
    if not writers_found:
        st.info("台本作家が登録されていません。")
    else:
        for writer_name in writers_found:
            if filter_writer and writer_name not in filter_writer:
                continue
            w_df = df_active[df_active["担当台本作家"].astype(str).str.strip() == writer_name]
            if w_df.empty:
                continue
            _person_scorecard(writer_name, w_df, "✏️", "台本提出期限", "台本提出日")

    st.markdown("---")

    # ── 編集者セクション ─────────────────────────────────────────────────────

    st.markdown("### 🎬 動画編集者 別 提出状況")

    editors_found = sorted([e for e in df_active["担当編集者"].dropna().unique() if str(e).strip()])
    if not editors_found:
        st.info("編集者が登録されていません。")
    else:
        for editor_name in editors_found:
            if filter_editor and editor_name not in filter_editor:
                continue
            e_df = df_active[df_active["担当編集者"].astype(str).str.strip() == editor_name]
            if e_df.empty:
                continue
            _person_scorecard(editor_name, e_df, "🎬", "動画提出期限", "動画提出日")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: 期限を一括設定（管理者向け）
# ══════════════════════════════════════════════════════════════════════════════

with tab_edit:
    st.markdown("### ✏️ 提出期限を設定・修正する")
    st.markdown("""
    <div style="background:#fef9c3;border-left:4px solid #f59e0b;
                padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
    案件を選択して、台本・動画の提出期限と実績日を設定・修正できます。<br>
    台本/動画URLが提出された際は <b>自動スタンプ</b> されますが、手動での修正も可能です。
    </div>
    """, unsafe_allow_html=True)

    # 案件選択
    df_sel = df_all[df_all["ステータス"] != "納品完了"].copy()
    df_sel = df_sel.sort_values("台本提出期限", na_position="last")

    if df_sel.empty:
        st.info("進行中の案件がありません。")
    else:
        # セレクトボックス用ラベル生成
        def _make_label(r) -> str:
            mgmt_s = str(r.get("管理番号", "") or "")
            title_s = str(r.get("案件名", "") or "無題")
            pfx = ("[" + mgmt_s + "] ") if mgmt_s else ""
            return pfx + title_s

        options_labels = ["— 案件を選択 —"] + [_make_label(r) for _, r in df_sel.iterrows()]
        options_ids    = [None] + list(df_sel["ID"].astype(str))

        sel_idx = st.selectbox(
            "案件を選択",
            range(len(options_labels)),
            format_func=lambda i: options_labels[i],
        )
        sel_id = options_ids[sel_idx]

        if sel_id:
            target = df_all[df_all["ID"].astype(str) == sel_id]
            if not target.empty:
                row = target.iloc[0]
                mgmt_s = str(row.get("管理番号", "") or "")
                pfx_s  = ("[" + mgmt_s + "] ") if mgmt_s else ""
                st.markdown(f"#### 📝 {pfx_s}{row.get('案件名', '無題')}")
                st.markdown(status_badge_html(str(row.get("ステータス", ""))), unsafe_allow_html=True)
                st.markdown("")

                with st.form("deadline_edit_form"):
                    st.markdown("##### ✏️ 台本")
                    td1, td2 = st.columns(2)
                    with td1:
                        sdl_val = row.get("台本提出期限")
                        sdl_def = sdl_val.date() if pd.notna(sdl_val) and hasattr(sdl_val, "date") else None
                        new_sdl = st.date_input("台本提出期限", value=sdl_def, key="sdl")
                    with td2:
                        ssub_val = row.get("台本提出日")
                        ssub_def = ssub_val.date() if pd.notna(ssub_val) and hasattr(ssub_val, "date") else None
                        new_ssub = st.date_input("台本提出日（実績）", value=ssub_def, key="ssub")

                    st.markdown("##### 🎬 動画")
                    vd1, vd2 = st.columns(2)
                    with vd1:
                        vdl_val = row.get("動画提出期限")
                        vdl_def = vdl_val.date() if pd.notna(vdl_val) and hasattr(vdl_val, "date") else None
                        new_vdl = st.date_input("動画提出期限", value=vdl_def, key="vdl")
                    with vd2:
                        vsub_val = row.get("動画提出日")
                        vsub_def = vsub_val.date() if pd.notna(vsub_val) and hasattr(vsub_val, "date") else None
                        new_vsub = st.date_input("動画提出日（実績）", value=vsub_def, key="vsub")

                    save_btn = st.form_submit_button("💾 保存する", use_container_width=True, type="primary")

                if save_btn:
                    try:
                        update_row(sel_id, {
                            "台本提出期限": new_sdl.strftime("%Y/%m/%d") if new_sdl else "",
                            "台本提出日":   new_ssub.strftime("%Y/%m/%d") if new_ssub else "",
                            "動画提出期限": new_vdl.strftime("%Y/%m/%d") if new_vdl else "",
                            "動画提出日":   new_vsub.strftime("%Y/%m/%d") if new_vsub else "",
                        })
                        st.success("✅ 提出期限・実績日を保存しました！")
                        clear_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 保存に失敗しました: {e}")
