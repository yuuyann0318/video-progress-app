"""
📋 案件管理（統合）

案件・リール・提出管理・リサーチをすべてこのページで完結。
役割に関係なく、誰でもすべての操作ができる。
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from utils.config import (
    STATUSES, STATUS_EMOJI, RESEARCH_GENRES,
    REEL_STATUSES, REEL_STATUS_EMOJI, REEL_STATUS_BG, REEL_STATUS_TEXT,
    PLATFORMS, PLATFORM_EMOJI, PLATFORM_COLOR,
    CONTENT_TYPES, REEL_ANALYTICS_COLS,
)
from utils.sheets import (
    load_data, update_row, add_row, delete_row, clear_cache, ensure_headers,
)
from utils.research import (
    load_research, add_research, evaluate_research, link_project,
    ensure_research_headers, extract_youtube_id, youtube_thumbnail,
)
from utils.reels import load_reels, add_reel, update_reel, clear_reel_cache, ensure_reel_headers
from utils.ui import (
    inject_css, render_project_cards, status_badge_html, days_label,
    reel_status_badge_html, platform_badge_html, paginate,
)
from utils.auth import render_auth_sidebar, is_authenticated

st.set_page_config(page_title="案件管理", page_icon="📋", layout="wide")
inject_css()
ensure_headers()
ensure_research_headers()
ensure_reel_headers()

# ── セッション状態の初期化 ────────────────────────────────────────────────────
for k, v in {
    "my_name": "",
    "selected_id": None,
    "research_preview_url": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
    st.markdown("### 🔍 フィルター（案件一覧）")
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
        clear_reel_cache()
        st.rerun()
    render_auth_sidebar()

# ── データ取得 ───────────────────────────────────────────────────────────────
is_editor = is_authenticated()
df = load_data()
today_ts = pd.Timestamp(date.today())
week_end = today_ts + pd.Timedelta(days=7)

# ── フィルター適用（案件一覧用）─────────────────────────────────────────────
view = df.copy()

if my_name.strip():
    n = my_name.strip()
    view = view[
        view["担当台本作家"].str.contains(n, na=False, case=False)
        | view["担当編集者"].str.contains(n, na=False, case=False)
    ]

if search.strip():
    q = search.strip()
    view = view[
        view["案件名"].str.contains(q, na=False, case=False)
        | view["管理番号"].str.contains(q, na=False, case=False)
        | view["担当台本作家"].str.contains(q, na=False, case=False)
        | view["担当編集者"].str.contains(q, na=False, case=False)
    ]

if status_filter:
    view = view[view["ステータス"].isin(status_filter)]

if hide_done:
    view = view[view["ステータス"] != "納品完了"]

if sort_opt == "納期が近い順":
    view = view.sort_values("納期", na_position="last")
elif sort_opt == "最終更新が新しい順":
    view = view.sort_values("最終更新日時", ascending=False, na_position="last")
elif sort_opt == "管理番号順":
    view = view.sort_values("管理番号", na_position="last")


# ════════════════════════════════════════════════════════════════════════════
# 共通ヘルパー関数
# ════════════════════════════════════════════════════════════════════════════

def _fmt_date(val) -> str:
    if pd.notna(val) and hasattr(val, "strftime"):
        return val.strftime("%Y/%m/%d")
    return "—"


def _submission_status(deadline, submitted_date, today) -> tuple:
    """Returns: (label, emoji, bg_color, text_color)"""
    has_sub = pd.notna(submitted_date)
    has_dl  = pd.notna(deadline)
    if has_sub:
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


def _int_val(r, col):
    v = r.get(col, 0)
    try:
        return int(float(str(v))) if str(v) not in ["", "nan", "None"] else 0
    except Exception:
        return 0


# ── 認証バナー ────────────────────────────────────────────────────────────────
if not is_editor:
    st.info("🔒 閲覧専用モード — 編集・追加するにはサイドバーからログインしてください")

# ── タブ ─────────────────────────────────────────────────────────────────────
tab_list, tab_new, tab_research, tab_reel, tab_submission = st.tabs([
    "📋 案件一覧", "➕ 新規登録", "🔍 リサーチ", "📱 リール管理", "📋 提出管理"
])


# ════════════════════════════════════════════════════════════════════════════
# Tab 1: 案件一覧（統合編集）
# ════════════════════════════════════════════════════════════════════════════
with tab_list:
    if my_name.strip():
        st.caption(f"👤 {my_name} の担当案件を表示中 / 全{len(view)}件")
    else:
        st.caption(f"全案件 {len(view)} 件（名前を入力すると自分の案件だけ絞り込めます）")

    left, right = st.columns([2, 3], gap="large")

    with left:
        selected_id = render_project_cards(view, st.session_state["selected_id"])
        st.session_state["selected_id"] = selected_id

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

                    due_val = row.get("納期")
                    new_due = st.date_input(
                        "納期",
                        value=due_val.date() if pd.notna(due_val) else None,
                    )

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

                    st.markdown("**📄 台本テキスト**")
                    new_script_text = st.text_area(
                        "台本テキスト",
                        value=str(row.get("台本テキスト", "") or ""),
                        height=300,
                        placeholder="ここに台本を貼り付けてください",
                        label_visibility="collapsed",
                    )

                    new_memo = st.text_area(
                        "備考", value=str(row.get("備考", "") or ""), height=80
                    )

                    submitted = st.form_submit_button("💾 保存", use_container_width=True, type="primary")

                if submitted and not is_editor:
                    st.error("🔒 保存するにはサイドバーからログインしてください")
                if submitted and is_editor:
                    auto_status = new_status
                    old_script_url = str(row.get("台本URL", "") or "")
                    old_final_url  = str(row.get("完パケ動画URL", "") or "")

                    if new_script_url and not old_script_url:
                        if new_status in ("未着手", "台本作成中"):
                            auto_status = "台本確認待ち"

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
                        "台本テキスト":   new_script_text,
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

                st.markdown("---")
                script_text_val = str(row.get("台本テキスト", "") or "")
                if script_text_val.strip():
                    st.markdown("### 📄 台本")
                    st.text_area(
                        "台本ビュー",
                        value=script_text_val,
                        height=500,
                        disabled=True,
                        label_visibility="collapsed",
                    )
                    st.markdown("---")

                if is_editor:
                    with st.expander("🗑️ この案件を削除する"):
                        st.warning(f"**「{title}」** をスプレッドシートから完全に削除します。この操作は元に戻せません。")
                        confirm_delete = st.checkbox("削除することを確認しました", key=f"confirm_del_{sel_id}")
                        if st.button("🗑️ 削除する", disabled=not confirm_delete, type="primary", key=f"do_del_{sel_id}"):
                            try:
                                delete_row(sel_id)
                                st.success(f"✅「{title}」を削除しました")
                                st.session_state["selected_id"] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 削除に失敗: {e}")


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
        if not is_editor:
            st.error("🔒 登録するにはサイドバーからログインしてください")
        elif not n_name.strip():
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

    with r_tab1:
        st.markdown("### 📤 参考動画を提出する")

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
            if not is_editor:
                st.error("🔒 提出するにはサイドバーからログインしてください")
            elif not r_title.strip() or not r_url.strip() or not r_point.strip() or not r_submitter.strip():
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

    with r_tab2:
        try:
            r_df = load_research()
        except Exception:
            st.error("リサーチデータの読み込みに失敗しました")
            st.stop()

        pending  = r_df[r_df["評価ステータス"] == "未評価"] if not r_df.empty else pd.DataFrame()
        approved = r_df[
            (r_df["評価ステータス"] == "採用") &
            (r_df["案件ID"].astype(str).str.strip().isin(["", "nan", "None"]))
        ] if not r_df.empty else pd.DataFrame()

        # ── 評価待ちキュー ────────────────────────────────────────────────────
        if pending.empty:
            st.success("🎉 評価待ちのリサーチはありません！")
        else:
            st.caption(f"評価待ち {len(pending)} 件 — 採用 / 不採用を決めると一覧から消えます")
            for _, r in pending.iterrows():
                r_id    = str(r.get("リサーチID", ""))
                r_title = str(r.get("動画タイトル", "—"))
                r_ch    = str(r.get("チャンネル名", "—"))
                r_url   = str(r.get("動画URL", ""))
                r_point = str(r.get("参考ポイント", ""))
                r_genre = str(r.get("ジャンル", ""))
                r_sub   = str(r.get("提出者", "—"))

                yt_id_r = extract_youtube_id(r_url)
                thumb   = youtube_thumbnail(yt_id_r) if yt_id_r else None

                c1, c2 = st.columns([1, 3])
                with c1:
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    if r_url:
                        st.markdown(f"[動画を開く →]({r_url})")
                with c2:
                    st.markdown(f"**{r_title}**")
                    st.caption(f"{r_ch}　|　{r_genre}　|　提出者: **{r_sub}**")
                    st.markdown(r_point)

                    ba, bb, bc = st.columns([2, 4, 1])
                    with ba:
                        if st.button("✅ 採用", key=f"adopt_{r_id}", use_container_width=True, type="primary"):
                            if not is_editor:
                                st.error("🔒 評価するにはログインが必要です")
                            else:
                                evaluate_research(r_id, "採用", my_name or "管理者", "")
                                clear_cache()
                                st.rerun()
                    with bb:
                        reject_comment = st.text_input(
                            "不採用コメント",
                            key=f"rc_{r_id}",
                            label_visibility="collapsed",
                            placeholder="不採用理由（任意）",
                        )
                    with bc:
                        if st.button("❌", key=f"reject_{r_id}", use_container_width=True):
                            if not is_editor:
                                st.error("🔒 評価するにはログインが必要です")
                            else:
                                evaluate_research(r_id, "不採用", my_name or "管理者", reject_comment)
                                clear_cache()
                                st.rerun()

                st.divider()

        # ── 採用済み・案件化待ち ──────────────────────────────────────────────
        if not approved.empty:
            with st.expander(f"📁 採用済み・案件化待ち　{len(approved)} 件"):
                for _, r in approved.iterrows():
                    r_id    = str(r.get("リサーチID", ""))
                    r_title = str(r.get("動画タイトル", "—"))
                    r_sub   = str(r.get("提出者", "—"))

                    st.markdown(f"**{r_title}**　（提出者: {r_sub}）")
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
                                format_func=lambda s: STATUS_EMOJI.get(s, "") + " " + s,
                                key=f"pstat_{r_id}",
                            )
                        p_ok = st.form_submit_button("📁 案件化する", type="primary")

                    if p_ok:
                        if not is_editor:
                            st.error("🔒 案件化するにはサイドバーからログインしてください")
                        elif not p_mgmt.strip() or not p_name.strip():
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

                    st.divider()


# ════════════════════════════════════════════════════════════════════════════
# Tab 4: リール管理
# ════════════════════════════════════════════════════════════════════════════
with tab_reel:
    st.markdown("## 📱 インスタリール / SNS投稿管理")

    # ── インラインフィルター ──────────────────────────────────────────────────
    with st.expander("🔍 フィルター・並び順", expanded=False):
        rf1, rf2, rf3 = st.columns(3)
        with rf1:
            reel_search_q = st.text_input(
                "タイトル / 管理番号 / 担当者",
                placeholder="例: R-001、田中",
                key="reel_search",
            )
            reel_sort_key = st.selectbox(
                "並び順",
                ["投稿予定日が近い順", "最終更新が新しい順", "管理番号順", "タイトル順"],
                key="reel_sort",
            )
        with rf2:
            reel_status_filter = st.multiselect(
                "ステータス", options=REEL_STATUSES,
                format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s, '')} {s}",
                key="reel_sf",
            )
            reel_platform_filter = st.multiselect(
                "プラットフォーム", options=PLATFORMS,
                format_func=lambda p: f"{PLATFORM_EMOJI.get(p, '')} {p}",
                key="reel_pf",
            )
        with rf3:
            reel_content_filter = st.multiselect(
                "コンテンツ種別", options=CONTENT_TYPES,
                key="reel_cf",
            )
            reel_hide_archived = st.checkbox("📦 アーカイブを非表示", value=True, key="reel_arc")
            reel_hide_posted   = st.checkbox("✅ 投稿済みを非表示",   value=False, key="reel_post")

    def _reel_apply_filters(df_: pd.DataFrame) -> pd.DataFrame:
        if reel_search_q:
            q = reel_search_q.lower()
            mask = (
                df_["タイトル"].astype(str).str.lower().str.contains(q) |
                df_["管理番号"].astype(str).str.lower().str.contains(q) |
                df_["担当台本作家"].astype(str).str.lower().str.contains(q) |
                df_["担当編集者"].astype(str).str.lower().str.contains(q)
            )
            df_ = df_[mask]
        if reel_status_filter:
            df_ = df_[df_["ステータス"].isin(reel_status_filter)]
        if reel_platform_filter:
            df_ = df_[df_["プラットフォーム"].isin(reel_platform_filter)]
        if reel_content_filter:
            df_ = df_[df_["コンテンツ種別"].isin(reel_content_filter)]
        if reel_hide_archived:
            df_ = df_[df_["ステータス"] != "アーカイブ"]
        if reel_hide_posted:
            df_ = df_[df_["ステータス"] != "投稿済み"]
        return df_

    def _reel_apply_sort(df_: pd.DataFrame) -> pd.DataFrame:
        if reel_sort_key == "投稿予定日が近い順":
            return df_.sort_values("投稿予定日", na_position="last")
        elif reel_sort_key == "最終更新が新しい順":
            return df_.sort_values("最終更新日時", ascending=False)
        elif reel_sort_key == "管理番号順":
            return df_.sort_values("管理番号")
        else:
            return df_.sort_values("タイトル")

    r_tab_dash, r_tab_list, r_tab_new, r_tab_analytics = st.tabs([
        "📊 ダッシュボード", "📋 リール一覧", "➕ 新規登録", "📈 パフォーマンス分析"
    ])

    # ── Tab 4-1: ダッシュボード ────────────────────────────────────────────────
    with r_tab_dash:
        df_reels_all = load_reels()
        reel_total    = len(df_reels_all[df_reels_all["ステータス"] != "アーカイブ"])
        reel_posted   = len(df_reels_all[df_reels_all["ステータス"] == "投稿済み"])
        reel_pipeline = reel_total - reel_posted
        reel_this_week = df_reels_all[
            (df_reels_all["投稿予定日"].notna()) &
            (df_reels_all["投稿予定日"] >= today_ts) &
            (df_reels_all["投稿予定日"] <= today_ts + pd.Timedelta(days=7)) &
            (df_reels_all["ステータス"] != "投稿済み")
        ]
        reel_today_posts = df_reels_all[
            (df_reels_all["投稿予定日"].notna()) &
            (df_reels_all["投稿予定日"] >= today_ts) &
            (df_reels_all["投稿予定日"] < today_ts + pd.Timedelta(days=1)) &
            (df_reels_all["ステータス"].isin(["投稿予定", "投稿済み"]))
        ]

        st.markdown("### 📊 KPIサマリー")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("📁 総リール数",      reel_total)
        k2.metric("🔄 制作パイプライン", reel_pipeline)
        k3.metric("✅ 投稿済み",         reel_posted)
        k4.metric("📅 今週の投稿予定",  len(reel_this_week))
        k5.metric("🔴 本日の投稿",      len(reel_today_posts))

        st.markdown("---")

        col_funnel, col_upcoming = st.columns([1, 1], gap="large")

        with col_funnel:
            st.markdown("#### 🔄 ステータス別パイプライン")
            status_counts = df_reels_all[df_reels_all["ステータス"] != "アーカイブ"]["ステータス"].value_counts()
            for st_name in REEL_STATUSES:
                if st_name == "アーカイブ":
                    continue
                count = status_counts.get(st_name, 0)
                if count == 0:
                    continue
                emoji    = REEL_STATUS_EMOJI.get(st_name, "")
                bg       = REEL_STATUS_BG.get(st_name, "#f3f4f6")
                color    = REEL_STATUS_TEXT.get(st_name, "#374151")
                bar_width = min(int(count / max(status_counts.max(), 1) * 100), 100)
                st.markdown(
                    f'<div style="display:flex;align-items:center;margin-bottom:6px;">'
                    f'<span style="width:130px;font-size:0.85em;font-weight:600;color:#374151;">'
                    f'{emoji} {st_name}</span>'
                    f'<div style="flex:1;background:#f1f5f9;border-radius:999px;height:18px;overflow:hidden;">'
                    f'<div style="width:{bar_width}%;background:{bg};height:100%;border-radius:999px;'
                    f'border:1px solid {color};"></div></div>'
                    f'<span style="width:28px;text-align:right;font-size:0.85em;font-weight:800;'
                    f'color:{color};margin-left:8px;">{count}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        with col_upcoming:
            st.markdown("#### 📅 今後7日間の投稿予定")
            if reel_this_week.empty:
                st.markdown("""
                <div style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;
                            padding:30px;text-align:center;color:#94a3b8;">
                    <div style="font-size:2.5em;">🎉</div>
                    <div style="margin-top:8px;">今週の投稿予定はありません</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                tw_sorted = reel_this_week.sort_values("投稿予定日")
                for _, rrow in tw_sorted.iterrows():
                    due    = rrow.get("投稿予定日")
                    due_str = due.strftime("%m/%d(%a)") if pd.notna(due) else "—"
                    plat   = str(rrow.get("プラットフォーム", ""))
                    plat_c = PLATFORM_COLOR.get(plat, "#7c3aed")
                    plat_e = PLATFORM_EMOJI.get(plat, "📲")
                    st_name = str(rrow.get("ステータス", ""))
                    st_bg   = REEL_STATUS_BG.get(st_name, "#f3f4f6")
                    st_e    = REEL_STATUS_EMOJI.get(st_name, "")
                    rtitle  = str(rrow.get("タイトル", ""))[:25]
                    mgmt    = str(rrow.get("管理番号", ""))
                    no_str  = f"[{mgmt}] " if mgmt else ""
                    st.markdown(
                        f'<div style="background:{st_bg};border-radius:10px;padding:10px 14px;'
                        f'margin-bottom:7px;border-left:4px solid {plat_c};">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<b style="font-size:0.9em;">{no_str}{rtitle}</b>'
                        f'<span style="background:{plat_c};color:white;padding:2px 8px;'
                        f'border-radius:999px;font-size:0.75em;font-weight:700;">'
                        f'{plat_e} {plat}</span>'
                        f'</div>'
                        f'<div style="margin-top:4px;font-size:0.8em;color:#64748b;">'
                        f'📅 {due_str} &nbsp; {st_e} {st_name}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("---")

        st.markdown("#### 📊 プラットフォーム別投稿数")
        df_reel_active = df_reels_all[df_reels_all["ステータス"] == "投稿済み"]
        if not df_reel_active.empty:
            plat_counts = df_reel_active["プラットフォーム"].value_counts()
            p_cols = st.columns(len(plat_counts))
            for i, (plat, cnt) in enumerate(plat_counts.items()):
                pcolor = PLATFORM_COLOR.get(str(plat), "#7c3aed")
                pemoji = PLATFORM_EMOJI.get(str(plat), "📲")
                p_cols[i].markdown(
                    f'<div style="background:white;border:2px solid {pcolor};border-radius:12px;'
                    f'padding:16px;text-align:center;">'
                    f'<div style="font-size:2em;">{pemoji}</div>'
                    f'<div style="font-size:1.6em;font-weight:800;color:{pcolor};">{cnt}</div>'
                    f'<div style="font-size:0.8em;color:#64748b;">{plat}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("📊 投稿済みのリールがまだありません。")

    # ── Tab 4-2: リール一覧 ────────────────────────────────────────────────────
    with r_tab_list:
        df_reels = load_reels()
        filtered_reels = _reel_apply_sort(_reel_apply_filters(df_reels))

        st.markdown(f"### 📋 リール一覧　`{len(filtered_reels)}` 件")

        if filtered_reels.empty:
            st.info("該当するリールがありません。フィルターを調整してください。")
        else:
            show_cols = {
                "管理番号":      "管理番号",
                "タイトル":      "タイトル",
                "ST":            "ステータス",
                "PF":            "プラットフォーム",
                "コンテンツ種別": "種別",
                "担当台本作家":  "台本作家",
                "担当編集者":    "編集者",
                "投稿予定":      "投稿予定日",
                "残り":          "残り",
            }

            def _reel_row_style(row):
                raw    = row.get("ステータス", "")
                status = next((s for s in REEL_STATUS_BG if s in raw), "")
                if status == "投稿済み":
                    return ["color:#94a3b8; font-style:italic"] * len(row)
                bg = REEL_STATUS_BG.get(status, "")
                return [f"background-color:{bg}"] * len(row)

            paged_reels = paginate(filtered_reels, key="reel_list")

            pdisp = paged_reels.copy()
            pdisp["投稿予定"] = pdisp["投稿予定日"].apply(
                lambda x: x.strftime("%Y/%m/%d") if pd.notna(x) else "—"
            )
            pdisp["残り"] = pdisp["投稿予定日"].apply(days_label)
            pdisp["ST"]   = pdisp["ステータス"].apply(
                lambda s: f"{REEL_STATUS_EMOJI.get(s, '')} {s}"
            )
            pdisp["PF"]   = pdisp["プラットフォーム"].apply(
                lambda p: f"{PLATFORM_EMOJI.get(p, '')} {p}"
            )

            render_cols = [c for c in show_cols if c in pdisp.columns]
            prender_df  = pdisp[render_cols].rename(columns=show_cols)
            pstyled     = prender_df.style.apply(_reel_row_style, axis=1)

            event = st.dataframe(
                pstyled,
                use_container_width=True,
                hide_index=True,
                height=min(48 * len(prender_df) + 48, 600),
                on_select="rerun",
                selection_mode="single-row",
                key="reel_table_df",
            )

            selected_rows  = event.selection.rows
            selected_reel  = pd.DataFrame()
            if selected_rows:
                selected_reel = paged_reels.iloc[[selected_rows[0]]]

            if not selected_reel.empty:
                rrow    = selected_reel.iloc[0]
                rrow_id = str(rrow["ID"])

                st.markdown("---")
                st.markdown(
                    f"### ✏️ 編集: **{rrow['タイトル']}** &nbsp; "
                    + reel_status_badge_html(str(rrow["ステータス"]))
                    + " &nbsp; " + platform_badge_html(str(rrow.get("プラットフォーム", ""))),
                    unsafe_allow_html=True,
                )

                with st.form(f"reel_edit_form_{rrow_id}"):
                    st.markdown("#### 📝 基本情報")
                    e1, e2, e3 = st.columns(3)
                    with e1:
                        re_mgmt   = st.text_input("管理番号", value=str(rrow.get("管理番号", "") or ""))
                    with e2:
                        re_title  = st.text_input("タイトル", value=str(rrow.get("タイトル", "") or ""))
                    with e3:
                        re_status = st.selectbox(
                            "ステータス", REEL_STATUSES,
                            index=REEL_STATUSES.index(rrow["ステータス"]) if rrow["ステータス"] in REEL_STATUSES else 0,
                            format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s, '')} {s}",
                        )

                    e4, e5, e6 = st.columns(3)
                    with e4:
                        re_platform = st.selectbox(
                            "プラットフォーム", PLATFORMS,
                            index=PLATFORMS.index(rrow.get("プラットフォーム")) if rrow.get("プラットフォーム") in PLATFORMS else 0,
                            format_func=lambda p: f"{PLATFORM_EMOJI.get(p, '')} {p}",
                        )
                    with e5:
                        re_content = st.selectbox(
                            "コンテンツ種別", CONTENT_TYPES,
                            index=CONTENT_TYPES.index(rrow.get("コンテンツ種別")) if rrow.get("コンテンツ種別") in CONTENT_TYPES else 0,
                        )
                    with e6:
                        re_series = st.text_input("シリーズ名", value=str(rrow.get("シリーズ名", "") or ""))

                    e7, e8 = st.columns(2)
                    with e7:
                        re_writer = st.text_input("担当台本作家", value=str(rrow.get("担当台本作家", "") or ""))
                    with e8:
                        re_editor = st.text_input("担当編集者",   value=str(rrow.get("担当編集者", "") or ""))

                    st.markdown("#### 📅 スケジュール")
                    s1, s2, s3 = st.columns(3)
                    with s1:
                        sched_val = rrow.get("投稿予定日")
                        sched_def = sched_val.date() if pd.notna(sched_val) and hasattr(sched_val, "date") else date.today()
                        re_sched  = st.date_input("投稿予定日", value=sched_def)
                    with s2:
                        re_time   = st.text_input("投稿時間 (HH:MM)", value=str(rrow.get("投稿時間", "") or ""), placeholder="例: 19:00")
                    with s3:
                        posted_val = rrow.get("投稿済み日")
                        posted_def = posted_val.date() if pd.notna(posted_val) and hasattr(posted_val, "date") else None
                        re_posted  = st.date_input("投稿済み日（任意）", value=posted_def)

                    st.markdown("#### 🔗 URL")
                    u1, u2 = st.columns(2)
                    with u1:
                        re_script   = st.text_input("台本URL",        value=str(rrow.get("台本URL", "") or ""))
                        re_material = st.text_input("素材フォルダURL", value=str(rrow.get("素材フォルダURL", "") or ""))
                    with u2:
                        re_final    = st.text_input("完パケURL",       value=str(rrow.get("完パケURL", "") or ""))
                        re_post_url = st.text_input("投稿URL（投稿済み後）", value=str(rrow.get("投稿URL", "") or ""))

                    st.markdown("#### 📝 Instagram投稿内容")
                    re_caption  = st.text_area("キャプション", value=str(rrow.get("キャプション", "") or ""), height=120, placeholder="投稿本文を入力...")
                    re_hashtags = st.text_area("ハッシュタグ",  value=str(rrow.get("ハッシュタグ", "") or ""),  height=80,  placeholder="#インスタグラム #リール ...")
                    re_music    = st.text_input("音楽・BGM",   value=str(rrow.get("音楽・BGM", "") or ""),   placeholder="例: オリジナル楽曲 / Trending Audio")

                    st.markdown("#### 📊 アナリティクス（投稿後に入力）")
                    ac1, ac2, ac3, ac4, ac5 = st.columns(5)
                    with ac1: re_views    = st.number_input("再生数",    value=_int_val(rrow, "再生数"),    min_value=0, step=100)
                    with ac2: re_likes    = st.number_input("いいね数",  value=_int_val(rrow, "いいね数"),  min_value=0, step=10)
                    with ac3: re_saves    = st.number_input("保存数",    value=_int_val(rrow, "保存数"),    min_value=0, step=10)
                    with ac4: re_comments = st.number_input("コメント数", value=_int_val(rrow, "コメント数"), min_value=0, step=1)
                    with ac5: re_reach    = st.number_input("リーチ数",  value=_int_val(rrow, "リーチ数"),  min_value=0, step=100)

                    re_notes   = st.text_area("備考", value=str(rrow.get("備考", "") or ""))
                    btn_update = st.form_submit_button("💾 更新する", use_container_width=True, type="primary")

                if btn_update and not is_editor:
                    st.error("🔒 更新するにはサイドバーからログインしてください")
                if btn_update and is_editor:
                    try:
                        posted_str = re_posted.strftime("%Y/%m/%d") if re_posted else ""
                        update_reel(rrow_id, {
                            "管理番号": re_mgmt, "タイトル": re_title, "ステータス": re_status,
                            "プラットフォーム": re_platform, "コンテンツ種別": re_content,
                            "シリーズ名": re_series,
                            "担当台本作家": re_writer, "担当編集者": re_editor,
                            "投稿予定日": re_sched.strftime("%Y/%m/%d"),
                            "投稿時間": re_time, "投稿済み日": posted_str,
                            "台本URL": re_script, "素材フォルダURL": re_material,
                            "完パケURL": re_final, "投稿URL": re_post_url,
                            "キャプション": re_caption, "ハッシュタグ": re_hashtags,
                            "音楽・BGM": re_music,
                            "再生数": str(re_views), "いいね数": str(re_likes),
                            "保存数": str(re_saves), "コメント数": str(re_comments),
                            "リーチ数": str(re_reach),
                            "備考": re_notes,
                        })
                        st.success(f"✅ 「{re_title}」を更新しました！")
                        if re_status == "投稿済み":
                            st.balloons()
                            st.markdown("### 🎉 投稿完了！お疲れ様でした！")
                    except Exception as e:
                        st.error(f"❌ 更新に失敗しました: {e}")

    # ── Tab 4-3: 新規登録 ─────────────────────────────────────────────────────
    with r_tab_new:
        st.markdown("### ➕ 新規リールを登録する")
        st.markdown("""
        <div style="background:#f0fdf4;border-left:4px solid #22c55e;
                    padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
        リールの企画段階から登録して、制作〜投稿まで一元管理しましょう。<br>
        <b>必須項目</b> だけ入力して登録し、あとから詳細を追記することもできます。
        </div>
        """, unsafe_allow_html=True)

        with st.form("new_reel_form", clear_on_submit=True):
            st.markdown("#### 📋 基本情報 *必須")
            n1, n2, n3 = st.columns(3)
            with n1: rn_mgmt    = st.text_input("管理番号 *", placeholder="例: R-001")
            with n2: rn_title   = st.text_input("タイトル *", placeholder="例: 【PR】〇〇商品紹介リール")
            with n3: rn_status  = st.selectbox(
                "初期ステータス", REEL_STATUSES,
                format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s, '')} {s}",
            )

            n4, n5, n6 = st.columns(3)
            with n4: rn_platform = st.selectbox(
                "プラットフォーム *", PLATFORMS,
                format_func=lambda p: f"{PLATFORM_EMOJI.get(p, '')} {p}",
            )
            with n5: rn_content  = st.selectbox("コンテンツ種別", CONTENT_TYPES)
            with n6: rn_series   = st.text_input("シリーズ名", placeholder="例: 週1回商品紹介シリーズ")

            st.markdown("#### 👥 担当者")
            t1, t2 = st.columns(2)
            with t1: rn_writer = st.text_input("担当台本作家", placeholder="例: 田中")
            with t2: rn_editor = st.text_input("担当編集者",   placeholder="例: 鈴木")

            st.markdown("#### 📅 スケジュール")
            d1, d2 = st.columns(2)
            with d1: rn_sched = st.date_input("投稿予定日 *", value=date.today() + timedelta(days=7))
            with d2: rn_time  = st.text_input("投稿時間 (HH:MM)", placeholder="例: 19:00")

            st.markdown("#### 📝 Instagram投稿内容（任意・後から編集可）")
            rn_caption  = st.text_area("キャプション", height=100, placeholder="投稿本文のドラフト...")
            rn_hashtags = st.text_area("ハッシュタグ",  height=60,  placeholder="#タグ1 #タグ2 ...")
            rn_music    = st.text_input("音楽・BGM", placeholder="例: オリジナル音声 / Trending Audio名")

            st.markdown("#### 🔗 URL（任意・後から追加可）")
            u1, u2 = st.columns(2)
            with u1:
                rn_script   = st.text_input("台本URL",        placeholder="Google Docs URL...")
                rn_material = st.text_input("素材フォルダURL", placeholder="Google Drive URL...")
            with u2:
                rn_final    = st.text_input("完パケURL",       placeholder="Google Drive URL...")
                rn_post_url = st.text_input("投稿URL",         placeholder="Instagram投稿URL...")

            rn_notes     = st.text_area("備考", placeholder="特記事項・クライアント要望など")
            btn_register = st.form_submit_button("📱 リールを登録する", use_container_width=True, type="primary")

        if btn_register:
            if not is_editor:
                st.error("🔒 登録するにはサイドバーからログインしてください")
            elif not rn_mgmt or not rn_title:
                st.error("⚠️ 管理番号とタイトルは必須です。")
            else:
                try:
                    reel_id = add_reel({
                        "管理番号": rn_mgmt, "タイトル": rn_title, "ステータス": rn_status,
                        "プラットフォーム": rn_platform, "コンテンツ種別": rn_content,
                        "シリーズ名": rn_series,
                        "担当台本作家": rn_writer, "担当編集者": rn_editor,
                        "投稿予定日": rn_sched.strftime("%Y/%m/%d"), "投稿時間": rn_time,
                        "台本URL": rn_script, "素材フォルダURL": rn_material,
                        "完パケURL": rn_final, "投稿URL": rn_post_url,
                        "キャプション": rn_caption, "ハッシュタグ": rn_hashtags,
                        "音楽・BGM": rn_music, "備考": rn_notes,
                    })
                    st.success(f"🎉 管理番号 [{rn_mgmt}]「{rn_title}」を登録しました！（ID: `{reel_id}`）")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ 登録に失敗しました: {e}")

    # ── Tab 4-4: パフォーマンス分析 ───────────────────────────────────────────
    with r_tab_analytics:
        df_analytics = load_reels()
        df_posted = df_analytics[
            (df_analytics["ステータス"] == "投稿済み") &
            (df_analytics["再生数"] > 0)
        ].copy()

        st.markdown("### 📈 パフォーマンス分析")

        if df_posted.empty:
            st.info("📊 アナリティクスデータがまだありません。\n\n投稿済みリールにアナリティクスを入力してください（リール一覧タブから編集できます）。")
        else:
            st.markdown("#### 🏆 累計パフォーマンス")
            total_posts    = len(df_posted)
            total_views    = int(df_posted["再生数"].sum())
            total_likes    = int(df_posted["いいね数"].sum())
            total_saves    = int(df_posted["保存数"].sum())
            avg_views      = int(df_posted["再生数"].mean())
            avg_engagement = round(
                ((df_posted["いいね数"] + df_posted["保存数"] + df_posted["コメント数"]) /
                 df_posted["再生数"].replace(0, 1) * 100).mean(), 2
            )

            ak1, ak2, ak3, ak4, ak5, ak6 = st.columns(6)
            ak1.metric("📱 投稿数",          total_posts)
            ak2.metric("▶️ 総再生数",        f"{total_views:,}")
            ak3.metric("❤️ 総いいね数",      f"{total_likes:,}")
            ak4.metric("🔖 総保存数",        f"{total_saves:,}")
            ak5.metric("📊 平均再生数",      f"{avg_views:,}")
            ak6.metric("💫 平均エンゲージ率", f"{avg_engagement}%")

            st.markdown("---")

            col_top, col_chart = st.columns([1, 1], gap="large")

            with col_top:
                st.markdown("#### 🥇 再生数ランキング TOP 10")
                top10 = df_posted.nlargest(10, "再生数")[
                    ["管理番号", "タイトル", "プラットフォーム", "再生数", "いいね数", "保存数"]
                ].reset_index(drop=True)
                medals = ["🥇", "🥈", "🥉"] + [str(i + 1) for i in range(3, 10)]
                for i, trow in top10.iterrows():
                    plat   = str(trow.get("プラットフォーム", ""))
                    plat_c = PLATFORM_COLOR.get(plat, "#7c3aed")
                    plat_e = PLATFORM_EMOJI.get(plat, "📲")
                    ttitle = str(trow.get("タイトル", ""))[:20]
                    views  = int(trow.get("再生数", 0))
                    likes  = int(trow.get("いいね数", 0))
                    saves  = int(trow.get("保存数", 0))
                    st.markdown(
                        f'<div style="display:flex;align-items:center;padding:8px 12px;'
                        f'border-radius:8px;margin-bottom:5px;background:#f8fafc;">'
                        f'<span style="font-size:1.3em;width:36px;">{medals[i]}</span>'
                        f'<div style="flex:1;">'
                        f'<b style="font-size:0.88em;">{ttitle}</b><br>'
                        f'<span style="font-size:0.75em;color:#64748b;">'
                        f'{plat_e} {plat} &nbsp;|&nbsp; ▶️ {views:,} &nbsp; ❤️ {likes:,} &nbsp; 🔖 {saves:,}'
                        f'</span></div></div>',
                        unsafe_allow_html=True,
                    )

            with col_chart:
                st.markdown("#### 📅 月別投稿数")
                df_posted["投稿月"] = pd.to_datetime(df_posted["投稿予定日"], errors="coerce").dt.to_period("M").astype(str)
                monthly = df_posted.groupby("投稿月").size().reset_index(name="投稿数")
                if not monthly.empty:
                    monthly = monthly.sort_values("投稿月")
                    st.bar_chart(monthly.set_index("投稿月")["投稿数"])
                else:
                    st.info("月別データを集計するには「投稿予定日」を入力してください。")

                st.markdown("#### 💫 エンゲージメント率（保存数/再生数）")
                df_posted["保存率"] = (
                    df_posted["保存数"] / df_posted["再生数"].replace(0, 1) * 100
                ).round(2)
                top_save = df_posted.nlargest(5, "保存率")[["タイトル", "保存率", "再生数"]].reset_index(drop=True)
                for _, srow in top_save.iterrows():
                    stitle = str(srow.get("タイトル", ""))[:18]
                    rate   = float(srow.get("保存率", 0))
                    bar_w  = min(int(rate * 10), 100)
                    st.markdown(
                        f'<div style="margin-bottom:8px;">'
                        f'<div style="display:flex;justify-content:space-between;'
                        f'font-size:0.8em;margin-bottom:2px;">'
                        f'<span>{stitle}</span><span style="font-weight:700;">{rate}%</span></div>'
                        f'<div style="background:#f1f5f9;border-radius:999px;height:10px;">'
                        f'<div style="width:{bar_w}%;background:#e1306c;height:100%;border-radius:999px;"></div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            st.markdown("#### 📊 プラットフォーム別 平均パフォーマンス比較")
            plat_perf = df_posted.groupby("プラットフォーム")[REEL_ANALYTICS_COLS].mean().round(0).astype(int)
            if not plat_perf.empty:
                plat_perf.columns = ["平均再生数", "平均いいね", "平均保存", "平均コメント", "平均リーチ"]
                st.dataframe(plat_perf, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# Tab 5: 提出管理
# ════════════════════════════════════════════════════════════════════════════
with tab_submission:
    st.markdown("## 📋 提出管理ダッシュボード")
    st.caption("台本・動画の提出期限と実績を担当者ごとに一元管理")

    if df.empty:
        st.warning("案件がまだ登録されていません。")
    else:
        # ── インラインフィルター ────────────────────────────────────────────────
        with st.expander("🔍 フィルター", expanded=False):
            sc1, sc2 = st.columns(2)
            with sc1:
                all_writers = sorted([w for w in df["担当台本作家"].dropna().unique() if str(w).strip()])
                all_editors = sorted([e for e in df["担当編集者"].dropna().unique() if str(e).strip()])
                sub_filter_writer = st.multiselect("台本作家", all_writers, key="sub_fw")
                sub_filter_editor = st.multiselect("編集者",   all_editors, key="sub_fe")
            with sc2:
                sub_hide_done      = st.checkbox("✅ 納品完了を非表示", value=True,  key="sub_hd")
                sub_only_overdue   = st.checkbox("🔴 期限超過のみ表示", value=False, key="sub_od")
                sub_only_this_week = st.checkbox("📅 今週期限のみ表示", value=False, key="sub_tw")

        # ── KPI ──────────────────────────────────────────────────────────────────
        df_kpi = df[df["ステータス"] != "納品完了"].copy()

        script_overdue   = len(df_kpi[df_kpi["台本提出期限"].notna() & (df_kpi["台本提出期限"] < today_ts) & df_kpi["台本提出日"].isna()])
        script_this_week = len(df_kpi[df_kpi["台本提出期限"].notna() & (df_kpi["台本提出期限"] >= today_ts) & (df_kpi["台本提出期限"] <= week_end) & df_kpi["台本提出日"].isna()])
        script_done      = len(df_kpi[df_kpi["台本提出日"].notna()])
        video_overdue    = len(df_kpi[df_kpi["動画提出期限"].notna() & (df_kpi["動画提出期限"] < today_ts) & df_kpi["動画提出日"].isna()])
        video_this_week  = len(df_kpi[df_kpi["動画提出期限"].notna() & (df_kpi["動画提出期限"] >= today_ts) & (df_kpi["動画提出期限"] <= week_end) & df_kpi["動画提出日"].isna()])
        video_done       = len(df_kpi[df_kpi["動画提出日"].notna()])

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("✏️ 台本 提出済み", script_done)
        k2.metric("🔴 台本 期限超過", script_overdue)
        k3.metric("📅 台本 今週期限", script_this_week)
        k4.metric("🎬 動画 提出済み", video_done)
        k5.metric("🔴 動画 期限超過", video_overdue)
        k6.metric("📅 動画 今週期限", video_this_week)

        st.markdown("---")

        # ── フィルター適用 ────────────────────────────────────────────────────
        sub_df = df.copy()
        if sub_hide_done:
            sub_df = sub_df[sub_df["ステータス"] != "納品完了"]
        if sub_filter_writer:
            sub_df = sub_df[sub_df["担当台本作家"].isin(sub_filter_writer)]
        if sub_filter_editor:
            sub_df = sub_df[sub_df["担当編集者"].isin(sub_filter_editor)]

        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📊 案件別ビュー", "👤 担当者別ビュー", "✏️ 期限を一括設定"])

        # ── 案件別ビュー ──────────────────────────────────────────────────────
        with sub_tab1:
            st.markdown(f"### 📊 案件別 提出状況一覧　`{len(sub_df)}` 件")

            if sub_df.empty:
                st.info("表示できる案件がありません。")
            else:
                sub_view = sub_df.copy()
                if sub_only_overdue:
                    mask = (
                        (sub_view["台本提出期限"].notna() & (sub_view["台本提出期限"] < today_ts) & sub_view["台本提出日"].isna()) |
                        (sub_view["動画提出期限"].notna() & (sub_view["動画提出期限"] < today_ts) & sub_view["動画提出日"].isna())
                    )
                    sub_view = sub_view[mask]
                if sub_only_this_week:
                    mask = (
                        (sub_view["台本提出期限"].notna() & (sub_view["台本提出期限"] >= today_ts) & (sub_view["台本提出期限"] <= week_end)) |
                        (sub_view["動画提出期限"].notna() & (sub_view["動画提出期限"] >= today_ts) & (sub_view["動画提出期限"] <= week_end))
                    )
                    sub_view = sub_view[mask]

                sub_view = sub_view.sort_values("台本提出期限", na_position="last").reset_index(drop=True)

                for _, row in sub_view.iterrows():
                    mgmt   = str(row.get("管理番号", "") or "")
                    stitle = str(row.get("案件名", "") or "無題")
                    status = str(row.get("ステータス", ""))
                    writer = str(row.get("担当台本作家", "") or "未定")
                    editor = str(row.get("担当編集者", "") or "未定")

                    s_dl  = row.get("台本提出期限")
                    s_sub = row.get("台本提出日")
                    v_dl  = row.get("動画提出期限")
                    v_sub = row.get("動画提出日")

                    s_label, s_emoji, s_bg, s_tc = _submission_status(s_dl, s_sub, today_ts)
                    v_label, v_emoji, v_bg, v_tc = _submission_status(v_dl, v_sub, today_ts)

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
                            st.markdown(f"**{label_no}{stitle}**")
                        with row_badge:
                            st.markdown(status_badge_html(status), unsafe_allow_html=True)

                        c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 2, 2])
                        with c1:
                            st.caption("✏️ 台本作家")
                            st.markdown(f"**{writer}**")
                        with c2:
                            st.caption("台本提出期限 → 実績")
                            st.markdown(
                                _fmt_date(s_dl) + " → " + _fmt_date(s_sub) + "&nbsp;&nbsp;" +
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
                            st.markdown(
                                _fmt_date(v_dl) + " → " + _fmt_date(v_sub) + "&nbsp;&nbsp;" +
                                _status_badge(v_label, v_emoji, v_bg, v_tc),
                                unsafe_allow_html=True,
                            )

                        st.markdown("</div>", unsafe_allow_html=True)

        # ── 担当者別ビュー ────────────────────────────────────────────────────
        with sub_tab2:
            def _person_scorecard(person_name: str, person_df: pd.DataFrame, role: str,
                                  dl_col: str, sub_col: str) -> None:
                total       = len(person_df)
                submitted_n = person_df[sub_col].notna().sum()
                overdue_n   = len(person_df[
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
                rate = int(submitted_n / total * 100) if total > 0 else 0
                border_color = "#ef4444" if overdue_n > 0 else ("#f59e0b" if this_week_n > 0 else "#10b981")

                st.markdown(
                    '<div style="border:2px solid ' + border_color + ';border-radius:14px;'
                    'padding:16px 20px;margin-bottom:16px;">',
                    unsafe_allow_html=True,
                )
                st.markdown(f"#### {role} **{person_name}**")

                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("📁 担当案件", total)
                sc2.metric("✅ 提出済み", int(submitted_n))
                sc3.metric("🔴 期限超過", int(overdue_n))
                sc4.metric("📅 今週期限", int(this_week_n))

                st.progress(rate / 100, text=f"提出率 {rate}%")

                with st.expander("案件一覧を見る"):
                    for _, r in person_df.sort_values(dl_col, na_position="last").iterrows():
                        mgmt_n  = str(r.get("管理番号", "") or "")
                        ttl     = str(r.get("案件名", "") or "無題")
                        label_n = ("[" + mgmt_n + "] ") if mgmt_n else ""
                        lbl, emo, bg, tc = _submission_status(r.get(dl_col), r.get(sub_col), today_ts)
                        st.markdown(
                            "- **" + label_n + ttl + "**　期限: " + _fmt_date(r.get(dl_col)) +
                            "　実績: " + _fmt_date(r.get(sub_col)) +
                            "　" + _status_badge(lbl, emo, bg, tc),
                            unsafe_allow_html=True,
                        )

                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("### ✏️ 台本作家 別 提出状況")
            df_active     = df[df["ステータス"] != "納品完了"].copy()
            writers_found = sorted([w for w in df_active["担当台本作家"].dropna().unique() if str(w).strip()])
            if not writers_found:
                st.info("台本作家が登録されていません。")
            else:
                for writer_name in writers_found:
                    if sub_filter_writer and writer_name not in sub_filter_writer:
                        continue
                    w_df = df_active[df_active["担当台本作家"].astype(str).str.strip() == writer_name]
                    if w_df.empty:
                        continue
                    _person_scorecard(writer_name, w_df, "✏️", "台本提出期限", "台本提出日")

            st.markdown("---")

            st.markdown("### 🎬 動画編集者 別 提出状況")
            editors_found = sorted([e for e in df_active["担当編集者"].dropna().unique() if str(e).strip()])
            if not editors_found:
                st.info("編集者が登録されていません。")
            else:
                for editor_name in editors_found:
                    if sub_filter_editor and editor_name not in sub_filter_editor:
                        continue
                    e_df = df_active[df_active["担当編集者"].astype(str).str.strip() == editor_name]
                    if e_df.empty:
                        continue
                    _person_scorecard(editor_name, e_df, "🎬", "動画提出期限", "動画提出日")

        # ── 期限一括設定 ──────────────────────────────────────────────────────
        with sub_tab3:
            st.markdown("### ✏️ 提出期限を設定・修正する")
            st.markdown("""
            <div style="background:#fef9c3;border-left:4px solid #f59e0b;
                        padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
            案件を選択して、台本・動画の提出期限と実績日を設定・修正できます。<br>
            台本/動画URLが提出された際は <b>自動スタンプ</b> されますが、手動での修正も可能です。
            </div>
            """, unsafe_allow_html=True)

            df_sel = df[df["ステータス"] != "納品完了"].copy()
            df_sel = df_sel.sort_values("台本提出期限", na_position="last")

            if df_sel.empty:
                st.info("進行中の案件がありません。")
            else:
                def _make_label(r) -> str:
                    mgmt_s  = str(r.get("管理番号", "") or "")
                    title_s = str(r.get("案件名", "") or "無題")
                    pfx = ("[" + mgmt_s + "] ") if mgmt_s else ""
                    return pfx + title_s

                options_labels = ["— 案件を選択 —"] + [_make_label(r) for _, r in df_sel.iterrows()]
                options_ids    = [None] + list(df_sel["ID"].astype(str))

                sel_idx = st.selectbox(
                    "案件を選択",
                    range(len(options_labels)),
                    format_func=lambda i: options_labels[i],
                    key="sub_sel_idx",
                )
                sel_id = options_ids[sel_idx]

                if sel_id:
                    target = df[df["ID"].astype(str) == sel_id]
                    if not target.empty:
                        row    = target.iloc[0]
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

                        if save_btn and not is_editor:
                            st.error("🔒 保存するにはサイドバーからログインしてください")
                        if save_btn and is_editor:
                            try:
                                update_row(sel_id, {
                                    "台本提出期限": new_sdl.strftime("%Y/%m/%d")  if new_sdl  else "",
                                    "台本提出日":   new_ssub.strftime("%Y/%m/%d") if new_ssub else "",
                                    "動画提出期限": new_vdl.strftime("%Y/%m/%d")  if new_vdl  else "",
                                    "動画提出日":   new_vsub.strftime("%Y/%m/%d") if new_vsub else "",
                                })
                                st.success("✅ 提出期限・実績日を保存しました！")
                                clear_cache()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 保存に失敗しました: {e}")
