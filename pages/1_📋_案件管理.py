"""
📋 案件管理（統合）

台本作成・動画編集・新規登録・リサーチを1ページで完結。
役割に関係なく、誰でもすべての操作ができる。
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

from utils.config import STATUSES, STATUS_EMOJI, RESEARCH_GENRES
from utils.sheets import (
    load_data, update_row, add_row, clear_cache, ensure_headers,
)
from utils.research import (
    load_research, add_research, evaluate_research, link_project,
    ensure_research_headers, extract_youtube_id, youtube_thumbnail,
)
from utils.ui import (
    inject_css, render_project_cards, status_badge_html, days_label,
)

st.set_page_config(page_title="案件管理", page_icon="📋", layout="wide")
inject_css()
ensure_headers()
ensure_research_headers()

# ── セッション状態の初期化 ────────────────────────────────────────────────────
if "my_name" not in st.session_state:
    st.session_state["my_name"] = ""
if "selected_id" not in st.session_state:
    st.session_state["selected_id"] = None
if "research_preview_url" not in st.session_state:
    st.session_state["research_preview_url"] = ""

# ── サイドバー ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 案件管理")
    st.markdown("---")

    st.markdown("### 👤 あなたの名前")
    my_name = st.text_input(
        "名前（任意）",
        value=st.session_state["my_name"],
        placeholder="例: 田中",
        help="入力すると担当案件だけ表示されます",
        key="sidebar_name",
    )
    st.session_state["my_name"] = my_name

    st.markdown("---")
    st.markdown("### 🔍 フィルター")
    search = st.text_input("検索", placeholder="案件名・管理番号")

    status_filter = st.multiselect(
        "ステータス",
        options=STATUSES,
        default=[],
        format_func=lambda s: STATUS_EMOJI.get(s, "") + " " + s,
    )
    hide_done = st.checkbox("納品完了を非表示", value=False)

    sort_opt = st.selectbox(
        "並び順",
        ["納期が近い順", "最終更新が新しい順", "管理番号順"],
    )

    st.markdown("---")
    if st.button("🔄 データ更新", use_container_width=True):
        clear_cache()
        st.rerun()

# ── データ取得 ───────────────────────────────────────────────────────────────
df = load_data()
today_ts = pd.Timestamp(date.today())

# ── フィルター適用 ────────────────────────────────────────────────────────────
view = df.copy()

# 名前フィルター（担当台本作家 OR 担当編集者 に一致）
if my_name.strip():
    n = my_name.strip()
    view = view[
        view["担当台本作家"].str.contains(n, na=False, case=False)
        | view["担当編集者"].str.contains(n, na=False, case=False)
    ]

# 検索フィルター
if search.strip():
    q = search.strip()
    view = view[
        view["案件名"].str.contains(q, na=False, case=False)
        | view["管理番号"].str.contains(q, na=False, case=False)
        | view["担当台本作家"].str.contains(q, na=False, case=False)
        | view["担当編集者"].str.contains(q, na=False, case=False)
    ]

# ステータスフィルター
if status_filter:
    view = view[view["ステータス"].isin(status_filter)]

# 納品完了非表示
if hide_done:
    view = view[view["ステータス"] != "納品完了"]

# 並び順
if sort_opt == "納期が近い順":
    view = view.sort_values("納期", na_position="last")
elif sort_opt == "最終更新が新しい順":
    view = view.sort_values("最終更新日時", ascending=False, na_position="last")
elif sort_opt == "管理番号順":
    view = view.sort_values("管理番号", na_position="last")

# ── タブ ─────────────────────────────────────────────────────────────────────
tab_list, tab_new, tab_research = st.tabs(["📋 案件一覧", "➕ 新規登録", "🔍 リサーチ"])


# ════════════════════════════════════════════════════════════════════════════
# Tab 1: 案件一覧（統合編集）
# ════════════════════════════════════════════════════════════════════════════
with tab_list:
    if my_name.strip():
        st.caption(f"👤 {my_name} の担当案件を表示中 / 全{len(view)}件")
    else:
        st.caption(f"全案件 {len(view)} 件（名前を入力すると自分の案件だけ絞り込めます）")

    left, right = st.columns([2, 3], gap="large")

    # ── 左: カードリスト ──────────────────────────────────────────────────────
    with left:
        selected_id = render_project_cards(view, st.session_state["selected_id"])
        st.session_state["selected_id"] = selected_id

    # ── 右: 編集フォーム ──────────────────────────────────────────────────────
    with right:
        sel_id = st.session_state["selected_id"]
        if not sel_id:
            st.info("👈 左の案件を選択すると編集できます")
        else:
            row_match = df[df["ID"] == sel_id]
            if row_match.empty:
                st.warning("案件が見つかりません。データを更新してください。")
            else:
                row = row_match.iloc[0]
                title = str(row.get("案件名", ""))
                st.markdown(f"### ✏️ {title}")
                st.markdown("---")

                with st.form(f"edit_{sel_id}"):
                    # ─ ステータス & 基本情報 ───────────────────────────────
                    fcol1, fcol2 = st.columns(2)
                    with fcol1:
                        new_status = st.selectbox(
                            "ステータス",
                            options=STATUSES,
                            index=STATUSES.index(row["ステータス"])
                            if row["ステータス"] in STATUSES else 0,
                            format_func=lambda s: STATUS_EMOJI.get(s, "") + " " + s,
                        )
                    with fcol2:
                        new_mgmt = st.text_input(
                            "管理番号", value=str(row.get("管理番号", "") or "")
                        )

                    fcol3, fcol4 = st.columns(2)
                    with fcol3:
                        new_writer = st.text_input(
                            "担当台本作家", value=str(row.get("担当台本作家", "") or "")
                        )
                    with fcol4:
                        new_editor = st.text_input(
                            "担当編集者", value=str(row.get("担当編集者", "") or "")
                        )

                    # 納期
                    due_val = row.get("納期")
                    new_due = st.date_input(
                        "納期",
                        value=due_val.date() if pd.notna(due_val) else None,
                    )

                    # ─ 台本提出 ────────────────────────────────────────────
                    st.markdown("**📝 台本**")
                    dcol1, dcol2 = st.columns(2)
                    with dcol1:
                        sdl_val = row.get("台本提出期限")
                        new_script_dl = st.date_input(
                            "台本提出期限",
                            value=sdl_val.date() if pd.notna(sdl_val) else None,
                            key="script_dl",
                        )
                    with dcol2:
                        sdt_val = row.get("台本提出日")
                        new_script_date = st.date_input(
                            "台本提出日（実績）",
                            value=sdt_val.date() if pd.notna(sdt_val) else None,
                            key="script_dt",
                        )
                    new_script_url = st.text_input(
                        "台本URL", value=str(row.get("台本URL", "") or ""),
                        placeholder="Google Docsなどのリンク"
                    )

                    # ─ 動画提出 ────────────────────────────────────────────
                    st.markdown("**🎬 動画**")
                    vcol1, vcol2 = st.columns(2)
                    with vcol1:
                        vdl_val = row.get("動画提出期限")
                        new_video_dl = st.date_input(
                            "動画提出期限",
                            value=vdl_val.date() if pd.notna(vdl_val) else None,
                            key="video_dl",
                        )
                    with vcol2:
                        vdt_val = row.get("動画提出日")
                        new_video_date = st.date_input(
                            "動画提出日（実績）",
                            value=vdt_val.date() if pd.notna(vdt_val) else None,
                            key="video_dt",
                        )
                    new_material_url = st.text_input(
                        "素材フォルダURL", value=str(row.get("素材フォルダURL", "") or ""),
                        placeholder="Google Driveなどのリンク"
                    )
                    new_final_url = st.text_input(
                        "完パケ動画URL", value=str(row.get("完パケ動画URL", "") or ""),
                        placeholder="完成動画のリンク"
                    )

                    # ─ 備考 ────────────────────────────────────────────────
                    new_memo = st.text_area(
                        "備考", value=str(row.get("備考", "") or ""), height=80
                    )

                    submitted = st.form_submit_button("💾 保存", use_container_width=True, type="primary")

                if submitted:
                    # 台本URL提出 → 自動ステータス変更
                    auto_status = new_status
                    old_script_url = str(row.get("台本URL", "") or "")
                    old_final_url  = str(row.get("完パケ動画URL", "") or "")

                    if new_script_url and not old_script_url:
                        if new_status in ("未着手", "台本作成中"):
                            auto_status = "台本確認待ち"

                    # 完パケURL提出 → 自動納品完了
                    if new_final_url and not old_final_url:
                        auto_status = "納品完了"

                    updates = {
                        "ステータス":      auto_status,
                        "管理番号":       new_mgmt,
                        "担当台本作家":   new_writer,
                        "担当編集者":     new_editor,
                        "納期":          str(new_due) if new_due else "",
                        "台本提出期限":   str(new_script_dl) if new_script_dl else "",
                        "台本提出日":     str(new_script_date) if new_script_date else "",
                        "台本URL":        new_script_url,
                        "動画提出期限":   str(new_video_dl) if new_video_dl else "",
                        "動画提出日":     str(new_video_date) if new_video_date else "",
                        "素材フォルダURL": new_material_url,
                        "完パケ動画URL":  new_final_url,
                        "備考":          new_memo,
                    }

                    try:
                        update_row(sel_id, updates)
                        if new_final_url and not old_final_url:
                            st.balloons()
                            st.success("🎉 納品完了！お疲れ様でした！")
                        else:
                            st.success("✅ 保存しました")
                        clear_cache()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 保存に失敗: {e}")


# ════════════════════════════════════════════════════════════════════════════
# Tab 2: 新規登録
# ════════════════════════════════════════════════════════════════════════════
with tab_new:
    st.markdown("### ➕ 新規案件登録")

    with st.form("new_case"):
        nc1, nc2 = st.columns(2)
        with nc1:
            n_mgmt   = st.text_input("管理番号", placeholder="例: 241")
            n_writer = st.text_input(
                "担当台本作家",
                value=my_name if my_name.strip() else "",
                placeholder="例: 田中",
            )
        with nc2:
            n_name   = st.text_input("案件名 *", placeholder="例: 【商品紹介】〇〇動画")
            n_editor = st.text_input("担当編集者", placeholder="例: 鈴木")

        nc3, nc4 = st.columns(2)
        with nc3:
            n_due = st.date_input("納期")
        with nc4:
            n_status = st.selectbox(
                "初期ステータス",
                options=STATUSES,
                format_func=lambda s: STATUS_EMOJI.get(s, "") + " " + s,
            )

        n5, n6 = st.columns(2)
        with n5:
            n_script_dl = st.date_input("台本提出期限（任意）", value=None)
        with n6:
            n_video_dl  = st.date_input("動画提出期限（任意）", value=None)

        n_memo = st.text_area("備考（任意）", height=70)

        reg = st.form_submit_button("📝 登録する", use_container_width=True, type="primary")

    if reg:
        if not n_name.strip():
            st.error("案件名は必須です")
        else:
            try:
                add_row({
                    "管理番号":    n_mgmt,
                    "案件名":      n_name,
                    "ステータス":  n_status,
                    "担当台本作家": n_writer,
                    "担当編集者":  n_editor,
                    "納期":        str(n_due) if n_due else "",
                    "台本提出期限": str(n_script_dl) if n_script_dl else "",
                    "動画提出期限": str(n_video_dl)  if n_video_dl  else "",
                    "備考":        n_memo,
                })
                st.success(f"✅「{n_name}」を登録しました！")
                clear_cache()
                st.rerun()
            except Exception as e:
                st.error(f"❌ 登録に失敗: {e}")


# ════════════════════════════════════════════════════════════════════════════
# Tab 3: リサーチ
# ════════════════════════════════════════════════════════════════════════════
with tab_research:
    r_tab1, r_tab2 = st.tabs(["📤 リサーチを提出する", "📋 評価・案件化する"])

    # ── リサーチ提出 ──────────────────────────────────────────────────────────
    with r_tab1:
        st.markdown("### 📤 参考動画を提出する")

        # YouTubeプレビュー
        preview_url = st.text_input(
            "YouTube URL（プレビュー確認用）",
            value=st.session_state["research_preview_url"],
            placeholder="https://www.youtube.com/watch?v=...",
            key="research_preview_input",
        )
        st.session_state["research_preview_url"] = preview_url

        yt_id = extract_youtube_id(preview_url) if preview_url else None
        if yt_id:
            thumb_url = youtube_thumbnail(yt_id)
            st.image(thumb_url, width=320)

        with st.form("research_form"):
            rf1, rf2 = st.columns(2)
            with rf1:
                r_title   = st.text_input("動画タイトル *", placeholder="参考にした動画タイトル")
                r_channel = st.text_input("チャンネル名", placeholder="チャンネル名")
            with rf2:
                r_url    = st.text_input("動画URL *", value=preview_url, placeholder="https://...")
                r_genre  = st.selectbox("ジャンル", options=RESEARCH_GENRES)

            r_point  = st.text_area("参考にしたいポイント *", placeholder="どこが参考になるか", height=90)
            r_submitter = st.text_input(
                "提出者名 *",
                value=my_name if my_name.strip() else "",
                placeholder="あなたの名前",
            )

            r_submit = st.form_submit_button("📤 提出する", use_container_width=True, type="primary")

        if r_submit:
            if not r_title.strip() or not r_url.strip() or not r_point.strip() or not r_submitter.strip():
                st.error("タイトル・URL・参考ポイント・提出者名は必須です")
            else:
                try:
                    add_research({
                        "動画タイトル":  r_title,
                        "動画URL":       r_url,
                        "チャンネル名":  r_channel,
                        "ジャンル":      r_genre,
                        "参考ポイント":  r_point,
                        "提出者":        r_submitter,
                    })
                    st.success("✅ リサーチを提出しました！")
                    st.session_state["research_preview_url"] = ""
                    clear_cache()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 提出に失敗: {e}")

    # ── リサーチ評価・案件化 ──────────────────────────────────────────────────
    with r_tab2:
        st.markdown("### 📋 リサーチを評価・案件化する")

        try:
            r_df = load_research()
        except Exception:
            st.error("リサーチデータの読み込みに失敗しました")
            st.stop()

        if r_df.empty:
            st.info("提出されたリサーチはありません。")
        else:
            eval_filter = st.selectbox(
                "表示フィルター",
                ["未評価のみ", "採用のみ", "すべて"],
                key="eval_filter",
            )
            if eval_filter == "未評価のみ":
                r_view = r_df[r_df["評価ステータス"] == "未評価"]
            elif eval_filter == "採用のみ":
                r_view = r_df[r_df["評価ステータス"] == "採用"]
            else:
                r_view = r_df.copy()

            evaluator = st.text_input(
                "評価者名",
                value=my_name if my_name.strip() else "",
                placeholder="あなたの名前",
                key="eval_name",
            )

            st.caption(f"{len(r_view)} 件表示")

            for _, r in r_view.iterrows():
                r_id     = str(r.get("リサーチID", ""))
                r_title  = str(r.get("動画タイトル", "—"))
                r_ch     = str(r.get("チャンネル名", "—"))
                r_url    = str(r.get("動画URL", ""))
                r_point  = str(r.get("参考ポイント", ""))
                r_genre  = str(r.get("ジャンル", ""))
                r_sub    = str(r.get("提出者", "—"))
                r_eval   = str(r.get("評価ステータス", "未評価"))
                r_proj   = str(r.get("案件ID", "") or "")

                # YouTube サムネイル
                yt_id_r = extract_youtube_id(r_url)
                thumb   = youtube_thumbnail(yt_id_r) if yt_id_r else None

                with st.expander(f"{'✅ ' if r_eval=='採用' else '❌ ' if r_eval=='不採用' else '🟡 '}{r_title}　— {r_sub}"):
                    ec1, ec2 = st.columns([1, 2])
                    with ec1:
                        if thumb:
                            st.image(thumb, use_container_width=True)
                        if r_url:
                            st.markdown(f"[動画を開く →]({r_url})")
                    with ec2:
                        st.markdown(f"**チャンネル:** {r_ch}")
                        st.markdown(f"**ジャンル:** {r_genre}")
                        st.markdown(f"**参考ポイント:** {r_point}")
                        st.markdown(f"**ステータス:** {r_eval}")

                    if r_eval == "未評価":
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            if st.button("✅ 採用", key=f"adopt_{r_id}", use_container_width=True, type="primary"):
                                evaluate_research(r_id, "採用", evaluator, "")
                                clear_cache()
                                st.rerun()
                        with ecol2:
                            reject_comment = st.text_input("不採用コメント（任意）", key=f"rc_{r_id}")
                            if st.button("❌ 不採用", key=f"reject_{r_id}", use_container_width=True):
                                evaluate_research(r_id, "不採用", evaluator, reject_comment)
                                clear_cache()
                                st.rerun()

                    elif r_eval == "採用" and not r_proj:
                        st.markdown("---")
                        st.markdown("**📁 案件化する**")
                        with st.form(f"proj_{r_id}"):
                            p1, p2 = st.columns(2)
                            with p1:
                                p_mgmt   = st.text_input("管理番号 *", key=f"pmgmt_{r_id}")
                                p_writer = st.text_input("担当台本作家", value=r_sub, key=f"pwrt_{r_id}")
                            with p2:
                                p_name   = st.text_input("案件名 *", value=r_title, key=f"pname_{r_id}")
                                p_editor = st.text_input("担当編集者", key=f"pedt_{r_id}")
                            p3, p4 = st.columns(2)
                            with p3:
                                p_due    = st.date_input("納期", key=f"pdue_{r_id}")
                            with p4:
                                p_status = st.selectbox(
                                    "初期ステータス", STATUSES,
                                    format_func=lambda s: STATUS_EMOJI.get(s,"")+" "+s,
                                    key=f"pstat_{r_id}",
                                )
                            p_ok = st.form_submit_button("📁 案件化する", type="primary")

                        if p_ok:
                            if not p_mgmt.strip() or not p_name.strip():
                                st.error("管理番号と案件名は必須です")
                            else:
                                try:
                                    add_row({
                                        "管理番号":    p_mgmt,
                                        "案件名":      p_name,
                                        "ステータス":  p_status,
                                        "担当台本作家": p_writer,
                                        "担当編集者":  p_editor,
                                        "納期":        str(p_due) if p_due else "",
                                    })
                                    new_df = load_data()
                                    match  = new_df[new_df["管理番号"] == p_mgmt]
                                    if not match.empty:
                                        link_project(r_id, match.iloc[0]["ID"])
                                    st.success(f"✅「{p_name}」を案件化しました！")
                                    clear_cache()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ 案件化に失敗: {e}")

                    elif r_eval == "採用" and r_proj:
                        st.success(f"✅ 案件化済み（案件ID: {r_proj}）")
