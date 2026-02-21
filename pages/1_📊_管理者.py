"""
管理者ページ（タブ構成）

Tab 1 — 📊 案件ダッシュボード
  KPI / 案件一覧（ページネーション・検索・フィルター・行選択編集）/ 新規登録

Tab 2 — 🔍 リサーチ評価
  台本作成者が提出したリサーチを確認・採用/不採用を判定
  採用済みリサーチからワンクリックで案件を登録
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.config import (
    STATUSES, STATUS_EMOJI, STATUS_BG,
    RESEARCH_STATUSES, RESEARCH_STATUS_BG, RESEARCH_STATUS_EMOJI, RESEARCH_GENRES,
)
from utils.sheets import load_data, add_row, update_row, clear_cache
from utils.research import (
    load_research, evaluate_research, link_project, clear_research_cache,
    extract_youtube_id, youtube_thumbnail, ensure_research_headers,
)
from utils.ui import inject_css, render_table, render_pipeline_bar, render_kanban_board, status_badge_html, days_label

# ─── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="管理者 | 動画制作管理",
    page_icon="📊",
    layout="wide",
)
inject_css()
ensure_research_headers()

# ─── セッション ───────────────────────────────────────────────────────────────

if "admin_reviewer" not in st.session_state:
    st.session_state["admin_reviewer"] = ""

# ─── サイドバー ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 管理者ダッシュボード")
    st.markdown("---")

    st.markdown("### 🔍 検索")
    search_query = st.text_input(
        "案件名 / 管理番号 / 担当者",
        placeholder="例: 235、田中、商品紹介",
        label_visibility="collapsed",
    )

    st.markdown("### 📋 フィルター")
    status_filter = st.multiselect(
        "ステータス", options=STATUSES,
        format_func=lambda s: f"{STATUS_EMOJI.get(s, '')} {s}",
    )

    df_all_sidebar = load_data()
    writers  = sorted([w for w in df_all_sidebar["担当台本作家"].dropna().unique() if w])
    editors  = sorted([e for e in df_all_sidebar["担当編集者"].dropna().unique() if e])
    writer_filter = st.multiselect("台本作家", options=writers)
    editor_filter = st.multiselect("編集者",   options=editors)

    st.markdown("### 🔃 並び順")
    sort_key = st.selectbox(
        "並び順",
        ["納期が近い順", "最終更新が新しい順", "管理番号順", "案件名順"],
        label_visibility="collapsed",
    )
    hide_done = st.checkbox("✅ 完了案件を非表示", value=False)

    st.markdown("---")
    st.markdown("### 👤 評価者名（リサーチ評価用）")
    reviewer_input = st.text_input(
        "評価者名", value=st.session_state["admin_reviewer"],
        placeholder="例: 山田（管理者）", label_visibility="collapsed",
    )
    if reviewer_input != st.session_state["admin_reviewer"]:
        st.session_state["admin_reviewer"] = reviewer_input

    st.markdown("---")
    if st.button("🔄 データを最新化", use_container_width=True):
        clear_cache()
        clear_research_cache()
        st.rerun()

# ─── タブ ────────────────────────────────────────────────────────────────────

st.markdown("## 📊 管理者ダッシュボード")

tab_projects, tab_kanban, tab_research = st.tabs(["📊 案件ダッシュボード", "🗂️ カンバンボード", "🔍 リサーチ評価"])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: 案件ダッシュボード
# ══════════════════════════════════════════════════════════════════════════════

with tab_projects:

    # ── データ取得 & フィルター ─────────────────────────────────────────────

    df = load_data()

    def apply_filters(df):
        if search_query:
            q = search_query.lower()
            mask = (
                df["案件名"].astype(str).str.lower().str.contains(q) |
                df["管理番号"].astype(str).str.lower().str.contains(q) |
                df["担当台本作家"].astype(str).str.lower().str.contains(q) |
                df["担当編集者"].astype(str).str.lower().str.contains(q)
            )
            df = df[mask]
        if status_filter:
            df = df[df["ステータス"].isin(status_filter)]
        if writer_filter:
            df = df[df["担当台本作家"].isin(writer_filter)]
        if editor_filter:
            df = df[df["担当編集者"].isin(editor_filter)]
        if hide_done:
            df = df[df["ステータス"] != "納品完了"]
        return df

    def apply_sort(df):
        if sort_key == "納期が近い順":      return df.sort_values("納期", na_position="last")
        elif sort_key == "最終更新が新しい順": return df.sort_values("最終更新日時", ascending=False)
        elif sort_key == "管理番号順":       return df.sort_values("管理番号")
        else:                                return df.sort_values("案件名")

    filtered_df = apply_sort(apply_filters(df))

    # ── KPI ────────────────────────────────────────────────────────────────

    today     = pd.Timestamp(date.today())
    total     = len(df)
    done      = len(df[df["ステータス"] == "納品完了"])
    in_prog   = total - done
    overdue   = len(df[(df["納期"].notna()) & (df["納期"] < today) & (df["ステータス"] != "納品完了")])
    due_soon  = len(df[(df["納期"].notna()) & (df["納期"] >= today) & (df["納期"] <= today + pd.Timedelta(days=7)) & (df["ステータス"] != "納品完了")])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📁 総案件数",  total)
    k2.metric("🔄 進行中",    in_prog)
    k3.metric("✅ 納品完了",  done)
    k4.metric("🔴 期限超過",  overdue)
    k5.metric("🟡 今週締切",  due_soon)

    # ── パイプラインバー ──────────────────────────────────────────────────────
    if not df.empty:
        render_pipeline_bar(df)

    st.markdown("---")

    # ── 案件テーブル（行選択編集）────────────────────────────────────────────

    st.markdown(f"### 📋 案件一覧　`{len(filtered_df)}` 件")
    selected_df = render_table(filtered_df, key="admin_table")

    # ── 選択行の編集フォーム ──────────────────────────────────────────────────

    if not selected_df.empty:
        row    = selected_df.iloc[0]
        row_id = str(row["ID"])

        st.markdown("---")
        st.markdown(f"### ✏️ 選択案件を編集: **{row['案件名']}**")
        st.markdown(status_badge_html(str(row["ステータス"])), unsafe_allow_html=True)
        st.markdown("")

        with st.form(f"edit_form_{row_id}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                new_mgmt_no = st.text_input("管理番号", value=str(row.get("管理番号", "") or ""), placeholder="例: 235")
            with c2:
                new_title   = st.text_input("案件名",   value=str(row.get("案件名", "") or ""))
            with c3:
                due_val     = row.get("納期")
                due_default = due_val.date() if pd.notna(due_val) and hasattr(due_val, "date") else date.today()
                new_due     = st.date_input("納期", value=due_default)

            c4, c5, c6 = st.columns(3)
            with c4:
                new_status = st.selectbox("ステータス", STATUSES,
                    index=STATUSES.index(row["ステータス"]) if row["ステータス"] in STATUSES else 0,
                    format_func=lambda s: f"{STATUS_EMOJI.get(s, '')} {s}")
            with c5:
                new_writer = st.text_input("担当台本作家", value=str(row.get("担当台本作家", "") or ""))
            with c6:
                new_editor = st.text_input("担当編集者",  value=str(row.get("担当編集者", "") or ""))

            st.markdown("#### 📅 提出期限")
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                script_dl_val = row.get("台本提出期限")
                script_dl_default = script_dl_val.date() if pd.notna(script_dl_val) and hasattr(script_dl_val, "date") else None
                new_script_dl = st.date_input("台本提出期限", value=script_dl_default)
            with d2:
                script_sub_val = row.get("台本提出日")
                script_sub_default = script_sub_val.date() if pd.notna(script_sub_val) and hasattr(script_sub_val, "date") else None
                new_script_sub = st.date_input("台本提出日（実績）", value=script_sub_default)
            with d3:
                video_dl_val = row.get("動画提出期限")
                video_dl_default = video_dl_val.date() if pd.notna(video_dl_val) and hasattr(video_dl_val, "date") else None
                new_video_dl = st.date_input("動画提出期限", value=video_dl_default)
            with d4:
                video_sub_val = row.get("動画提出日")
                video_sub_default = video_sub_val.date() if pd.notna(video_sub_val) and hasattr(video_sub_val, "date") else None
                new_video_sub = st.date_input("動画提出日（実績）", value=video_sub_default)

            st.markdown("#### 🔗 URL")
            u1, u2, u3 = st.columns(3)
            with u1: new_script   = st.text_input("台本URL",       value=str(row.get("台本URL", "") or ""))
            with u2: new_material = st.text_input("素材フォルダURL", value=str(row.get("素材フォルダURL", "") or ""))
            with u3: new_final    = st.text_input("完パケ動画URL",  value=str(row.get("完パケ動画URL", "") or ""))

            new_notes = st.text_area("備考", value=str(row.get("備考", "") or ""))
            btn_update = st.form_submit_button("💾 更新する", use_container_width=True, type="primary")

        if btn_update:
            try:
                update_row(row_id, {
                    "管理番号": new_mgmt_no, "案件名": new_title, "ステータス": new_status,
                    "担当台本作家": new_writer, "担当編集者": new_editor,
                    "納期": new_due.strftime("%Y/%m/%d"),
                    "台本提出期限": new_script_dl.strftime("%Y/%m/%d") if new_script_dl else "",
                    "台本提出日":   new_script_sub.strftime("%Y/%m/%d") if new_script_sub else "",
                    "動画提出期限": new_video_dl.strftime("%Y/%m/%d") if new_video_dl else "",
                    "動画提出日":   new_video_sub.strftime("%Y/%m/%d") if new_video_sub else "",
                    "台本URL": new_script, "素材フォルダURL": new_material, "完パケ動画URL": new_final,
                    "備考": new_notes,
                })
                st.success(f"✅ 「{new_title}」を更新しました！")
                if new_status == "納品完了":
                    st.balloons()
            except Exception as e:
                st.error(f"❌ 更新に失敗しました: {e}")

    # ── 新規案件登録 ──────────────────────────────────────────────────────────

    st.markdown("---")
    with st.expander("➕ 新規案件を登録する", expanded=False):
        with st.form("new_project_form"):
            st.markdown("#### 基本情報")
            n1, n2, n3 = st.columns(3)
            with n1: new_mgmt      = st.text_input("管理番号 *", placeholder="例: 239")
            with n2: new_name      = st.text_input("案件名 *",   placeholder="例: 【商品紹介】〇〇リール")
            with n3: new_due_reg   = st.date_input("納期 *", min_value=date.today())

            n4, n5, n6 = st.columns(3)
            with n4: new_status_reg = st.selectbox("初期ステータス", STATUSES, format_func=lambda s: f"{STATUS_EMOJI.get(s,'')} {s}")
            with n5: new_writer_reg = st.text_input("担当台本作家", placeholder="例: 田中")
            with n6: new_editor_reg = st.text_input("担当編集者",  placeholder="例: 鈴木")

            st.markdown("#### 📅 提出期限（任意）")
            nd1, nd2 = st.columns(2)
            with nd1: new_script_dl_reg = st.date_input("台本提出期限", value=None)
            with nd2: new_video_dl_reg  = st.date_input("動画提出期限", value=None)

            new_notes_reg = st.text_area("備考", placeholder="特記事項があれば")
            submitted = st.form_submit_button("📝 登録する", use_container_width=True, type="primary")

        if submitted:
            if not new_mgmt or not new_name:
                st.error("管理番号と案件名は必須です。")
            else:
                try:
                    add_row({
                        "管理番号": new_mgmt, "案件名": new_name, "ステータス": new_status_reg,
                        "担当台本作家": new_writer_reg, "担当編集者": new_editor_reg,
                        "納期": new_due_reg.strftime("%Y/%m/%d"),
                        "台本提出期限": new_script_dl_reg.strftime("%Y/%m/%d") if new_script_dl_reg else "",
                        "動画提出期限": new_video_dl_reg.strftime("%Y/%m/%d") if new_video_dl_reg else "",
                        "備考": new_notes_reg,
                    })
                    st.success(f"✅ 管理番号 [{new_mgmt}]「{new_name}」を登録しました！")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ 登録に失敗しました: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: カンバンボード
# ══════════════════════════════════════════════════════════════════════════════

with tab_kanban:

    df_kb = load_data()

    # ─ フィルター（カンバン専用）───────────────────────────────────────────
    kb_c1, kb_c2, kb_c3 = st.columns([2, 1, 1])
    with kb_c1:
        kb_search = st.text_input(
            "🔍 案件名 / 担当者 で絞り込み",
            placeholder="例: 商品紹介、田中",
            key="kb_search",
            label_visibility="collapsed",
        )
    with kb_c2:
        kb_writer = st.selectbox(
            "台本作家",
            ["全員"] + sorted([w for w in df_kb["担当台本作家"].dropna().unique() if w]),
            key="kb_writer",
            label_visibility="collapsed",
        )
    with kb_c3:
        kb_hide_done = st.checkbox("✅ 納品完了を非表示", value=True, key="kb_hide_done")

    df_kb_filtered = df_kb.copy()
    if kb_search:
        q = kb_search.lower()
        df_kb_filtered = df_kb_filtered[
            df_kb_filtered["案件名"].astype(str).str.lower().str.contains(q) |
            df_kb_filtered["担当台本作家"].astype(str).str.lower().str.contains(q) |
            df_kb_filtered["担当編集者"].astype(str).str.lower().str.contains(q)
        ]
    if kb_writer != "全員":
        df_kb_filtered = df_kb_filtered[df_kb_filtered["担当台本作家"] == kb_writer]
    if kb_hide_done:
        df_kb_filtered = df_kb_filtered[df_kb_filtered["ステータス"] != "納品完了"]

    # ─ パイプラインバー ────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.72em;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.1em;color:#94a3b8;margin-bottom:10px;padding-bottom:6px;'
        'border-bottom:1px solid #e2e8f0;">📊 パイプライン分布</div>',
        unsafe_allow_html=True,
    )
    if not df_kb_filtered.empty:
        render_pipeline_bar(df_kb_filtered)
    st.markdown("<br>", unsafe_allow_html=True)

    # ─ カンバンボード ──────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.72em;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.1em;color:#94a3b8;margin-bottom:10px;padding-bottom:6px;'
        'border-bottom:1px solid #e2e8f0;">🗂️ カンバンボード</div>',
        unsafe_allow_html=True,
    )
    render_kanban_board(df_kb_filtered)

    st.caption(
        "📌 カンバンボードは読み取り専用です。案件の編集は「📊 案件ダッシュボード」タブから行ってください。"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: リサーチ評価
# ══════════════════════════════════════════════════════════════════════════════

with tab_research:

    reviewer_name = st.session_state["admin_reviewer"].strip()

    st.markdown("### 🔍 リサーチ評価・案件化")
    st.markdown("""
    <div style="background:#fef9c3;border-left:4px solid #f59e0b;
                padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
    台本作成者から提出されたリサーチを確認し、<b>採用 / 不採用</b> を判定してください。<br>
    採用したリサーチは <b>そのまま新規案件として登録</b> できます。
    </div>
    """, unsafe_allow_html=True)

    if not reviewer_name:
        st.warning("👈 サイドバーの「評価者名」を入力してから評価してください。")

    # ── フィルター ────────────────────────────────────────────────────────────

    rf1, rf2 = st.columns([2, 1])
    with rf1:
        r_status_filter = st.multiselect(
            "評価ステータスで絞り込み",
            RESEARCH_STATUSES,
            default=["未評価"],
            format_func=lambda s: f"{RESEARCH_STATUS_EMOJI.get(s, '')} {s}",
        )
    with rf2:
        r_sort = st.selectbox("並び順", ["提出日時が新しい順", "提出日時が古い順", "提出者順"])

    df_r = load_research()

    if df_r.empty:
        st.info("まだリサーチが提出されていません。")
        st.stop()

    # フィルター適用
    if r_status_filter:
        df_r = df_r[df_r["評価ステータス"].isin(r_status_filter)]
    if r_sort == "提出日時が新しい順":
        df_r = df_r.sort_values("提出日時", ascending=False)
    elif r_sort == "提出日時が古い順":
        df_r = df_r.sort_values("提出日時", ascending=True)
    else:
        df_r = df_r.sort_values("提出者")

    df_r = df_r.reset_index(drop=True)

    # KPI
    df_all_r = load_research()
    rk1, rk2, rk3, rk4 = st.columns(4)
    rk1.metric("📥 提出総数",  len(df_all_r))
    rk2.metric("🟡 未評価",    len(df_all_r[df_all_r["評価ステータス"] == "未評価"]))
    rk3.metric("✅ 採用済み",  len(df_all_r[df_all_r["評価ステータス"] == "採用"]))
    rk4.metric("❌ 不採用",   len(df_all_r[df_all_r["評価ステータス"] == "不採用"]))

    st.markdown(f"---\n**{len(df_r)} 件表示中**")

    # ── リサーチカード一覧 ────────────────────────────────────────────────────

    for idx, r in df_r.iterrows():
        research_id  = str(r.get("リサーチID", ""))
        title        = str(r.get("動画タイトル", "タイトルなし"))
        url          = str(r.get("動画URL", ""))
        channel      = str(r.get("チャンネル名", ""))
        point        = str(r.get("参考ポイント", ""))
        genre        = str(r.get("ジャンル", ""))
        submitter    = str(r.get("提出者", ""))
        eval_status  = str(r.get("評価ステータス", "未評価"))
        eval_comment = str(r.get("評価コメント", ""))
        linked_id    = str(r.get("案件ID", ""))
        submitted_at = r.get("提出日時")
        date_str     = submitted_at.strftime("%Y/%m/%d") if pd.notna(submitted_at) else "—"

        vid_id = extract_youtube_id(url)
        thumb  = youtube_thumbnail(vid_id, "mq") if vid_id else None

        # カード背景色
        card_bg = RESEARCH_STATUS_BG.get(eval_status, "#ffffff")
        status_icon = RESEARCH_STATUS_EMOJI.get(eval_status, "🟡")

        with st.container():
            st.markdown(
                f'<div style="background:{card_bg};border-radius:12px;'
                f'border:1px solid #e2e8f0;padding:4px;margin-bottom:8px;">',
                unsafe_allow_html=True,
            )

            card_c1, card_c2 = st.columns([1, 4])

            with card_c1:
                if thumb:
                    st.image(thumb, use_container_width=True)
                    st.caption("🎬 YouTube")
                else:
                    st.markdown("""
                    <div style="background:#e2e8f0;border-radius:8px;
                                padding:24px 8px;text-align:center;color:#9ca3af;">
                        🔗
                    </div>""", unsafe_allow_html=True)

            with card_c2:
                # ヘッダー行
                hdr_c1, hdr_c2 = st.columns([3, 1])
                with hdr_c1:
                    st.markdown(f"**{title}**")
                    st.caption(
                        f"チャンネル: {channel or '—'}　／　ジャンル: {genre}　／　"
                        f"提出者: **{submitter}**　提出日: {date_str}"
                    )
                with hdr_c2:
                    st.markdown(
                        f'<span style="background:{card_bg};padding:3px 10px;'
                        f'border-radius:999px;font-size:0.85em;font-weight:700;">'
                        f'{status_icon} {eval_status}</span>',
                        unsafe_allow_html=True,
                    )

                # 参考ポイント
                st.markdown(f"📝 **参考ポイント:** {point}")

                if url:
                    st.markdown(f"🔗 [動画を開く]({url})")

                # 採用済みで案件化済みなら表示
                if eval_status == "採用" and linked_id:
                    st.success(f"🎉 案件化済み　案件ID: `{linked_id}`")
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("---")
                    continue

                # 不採用のコメント表示
                if eval_status == "不採用" and eval_comment:
                    st.warning(f"評価コメント: {eval_comment}")

            st.markdown('</div>', unsafe_allow_html=True)

        # ── 評価アクション（未評価のもののみ）────────────────────────────────

        if eval_status == "未評価":
            action_c1, action_c2 = st.columns([1, 1])

            # 採用フォーム
            with action_c1:
                with st.expander("✅ 採用する → 案件を登録", expanded=False):
                    with st.form(f"adopt_form_{research_id}"):
                        st.markdown("##### 案件情報を入力して採用登録")
                        a1, a2 = st.columns(2)
                        with a1: adopt_mgmt   = st.text_input("管理番号 *", placeholder="例: 240", key=f"amgmt_{research_id}")
                        with a2: adopt_name   = st.text_input("案件名 *",   value=title,            key=f"aname_{research_id}")
                        a3, a4 = st.columns(2)
                        with a3: adopt_writer = st.text_input("担当台本作家", value=submitter,       key=f"awriter_{research_id}")
                        with a4: adopt_editor = st.text_input("担当編集者",  placeholder="例: 鈴木", key=f"aeditor_{research_id}")
                        adopt_due    = st.date_input("納期 *", min_value=date.today(), key=f"adue_{research_id}")
                        adopt_status = st.selectbox("初期ステータス", STATUSES,
                            format_func=lambda s: f"{STATUS_EMOJI.get(s,'')}{s}", key=f"ast_{research_id}")
                        adopt_notes  = st.text_area("備考", value=f"参考: {url}", key=f"anotes_{research_id}")
                        adopt_comment = st.text_input("採用コメント（任意）", placeholder="良い点など", key=f"acom_{research_id}")
                        btn_adopt = st.form_submit_button("✅ 採用して案件登録", use_container_width=True, type="primary")

                    if btn_adopt:
                        if not adopt_mgmt or not adopt_name:
                            st.error("管理番号と案件名は必須です。")
                        elif not reviewer_name:
                            st.error("サイドバーに評価者名を入力してください。")
                        else:
                            try:
                                # 案件を登録
                                from utils.sheets import generate_id as gen_id
                                new_pid = gen_id()
                                add_row({
                                    "ID":        new_pid,
                                    "管理番号":  adopt_mgmt,
                                    "案件名":    adopt_name,
                                    "ステータス": adopt_status,
                                    "担当台本作家": adopt_writer,
                                    "担当編集者":  adopt_editor,
                                    "納期":      adopt_due.strftime("%Y/%m/%d"),
                                    "備考":      adopt_notes,
                                })
                                # リサーチを採用に更新 & 案件IDを紐付け
                                evaluate_research(research_id, "採用", reviewer_name, adopt_comment)
                                link_project(research_id, new_pid)
                                st.success(f"🎉 採用！管理番号[{adopt_mgmt}]「{adopt_name}」を登録しました！")
                                st.balloons()
                            except Exception as e:
                                st.error(f"❌ 登録に失敗しました: {e}")

            # 不採用フォーム
            with action_c2:
                with st.expander("❌ 不採用にする", expanded=False):
                    with st.form(f"reject_form_{research_id}"):
                        st.markdown("##### 不採用の理由（任意）")
                        reject_comment = st.text_area(
                            "コメント",
                            placeholder="例: 既存の案件と類似 / ターゲット層が合わない",
                            key=f"rcom_{research_id}",
                        )
                        btn_reject = st.form_submit_button("❌ 不採用にする", use_container_width=True)

                    if btn_reject:
                        if not reviewer_name:
                            st.error("サイドバーに評価者名を入力してください。")
                        else:
                            try:
                                evaluate_research(research_id, "不採用", reviewer_name, reject_comment)
                                st.warning(f"「{title}」を不採用にしました。")
                            except Exception as e:
                                st.error(f"❌ 更新に失敗しました: {e}")

        # 採用済みで未案件化（リンクなし）の場合のみ案件化ボタンを表示
        elif eval_status == "採用" and not linked_id:
            with st.expander("📋 案件を登録する（採用済み）", expanded=False):
                with st.form(f"convert_form_{research_id}"):
                    b1, b2 = st.columns(2)
                    with b1: conv_mgmt   = st.text_input("管理番号 *", key=f"cmgmt_{research_id}")
                    with b2: conv_name   = st.text_input("案件名 *",   value=title, key=f"cname_{research_id}")
                    b3, b4 = st.columns(2)
                    with b3: conv_writer = st.text_input("担当台本作家", value=submitter, key=f"cwriter_{research_id}")
                    with b4: conv_editor = st.text_input("担当編集者",  key=f"ceditor_{research_id}")
                    conv_due = st.date_input("納期 *", min_value=date.today(), key=f"cdue_{research_id}")
                    conv_notes = st.text_area("備考", value=f"参考: {url}", key=f"cnotes_{research_id}")
                    btn_conv = st.form_submit_button("📋 案件を登録する", use_container_width=True, type="primary")

                if btn_conv:
                    if not conv_mgmt or not conv_name:
                        st.error("管理番号と案件名は必須です。")
                    else:
                        try:
                            from utils.sheets import generate_id as gen_id
                            new_pid = gen_id()
                            add_row({
                                "ID": new_pid, "管理番号": conv_mgmt, "案件名": conv_name,
                                "ステータス": "未着手", "担当台本作家": conv_writer,
                                "担当編集者": conv_editor, "納期": conv_due.strftime("%Y/%m/%d"),
                                "備考": conv_notes,
                            })
                            link_project(research_id, new_pid)
                            st.success(f"📋 案件を登録しました！")
                            st.balloons()
                        except Exception as e:
                            st.error(f"❌ 登録に失敗しました: {e}")

        st.markdown("---")
