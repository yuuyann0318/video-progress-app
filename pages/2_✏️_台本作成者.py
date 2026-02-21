"""
台本作成者ページ（タブ構成）

Tab 1 — 📝 担当案件
  自分の担当案件から台本URLを提出し、ステータスを更新する

Tab 2 — 🔍 リサーチ提出
  参考動画URLとポイントを提出する
  YouTubeの場合はサムネイルをプレビュー表示
  提出されたリサーチは管理者が評価し、採用されたものが案件化される

Tab 3 — 📱 担当リール
  リール台本URLの提出・ステータス更新
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.config import (
    STATUSES, WRITER_STATUSES, STATUS_EMOJI, RESEARCH_GENRES,
    REEL_STATUS_EMOJI, REEL_STATUS_BG, REEL_WRITER_STATUSES,
    PLATFORM_EMOJI,
)
from utils.sheets import load_data, add_row, update_row, clear_cache
from utils.reels import load_reels, update_reel, clear_reel_cache, ensure_reel_headers
from utils.research import (
    load_research, add_research, clear_research_cache,
    extract_youtube_id, youtube_thumbnail, is_youtube_url,
    ensure_research_headers,
)
from utils.ui import (
    inject_css, render_project_cards, render_reel_cards,
    status_badge_html, reel_status_badge_html, platform_badge_html,
    days_label,
)

# ─── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="台本作成者 | 動画制作管理",
    page_icon="✏️",
    layout="wide",
)
inject_css()
ensure_research_headers()
ensure_reel_headers()

# ─── セッション初期化 ──────────────────────────────────────────────────────────

if "writer_name"             not in st.session_state: st.session_state["writer_name"]             = ""
if "writer_selected_id"      not in st.session_state: st.session_state["writer_selected_id"]      = None
if "research_preview_url"    not in st.session_state: st.session_state["research_preview_url"]    = ""
if "reel_writer_selected_id" not in st.session_state: st.session_state["reel_writer_selected_id"] = None

# ─── サイドバー ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ✏️ 台本作成者")
    st.markdown("---")

    st.markdown("### あなたの名前")
    name_input = st.text_input(
        "名前", value=st.session_state["writer_name"],
        placeholder="例: 田中", label_visibility="collapsed",
    )
    if name_input != st.session_state["writer_name"]:
        st.session_state["writer_name"] = name_input
        st.session_state["writer_selected_id"] = None

    st.markdown("---")
    show_all = st.checkbox("全案件を表示（担当外も含む）", value=False)
    st.markdown("---")

    if st.button("🔄 データを最新化", use_container_width=True):
        clear_cache()
        clear_research_cache()
        clear_reel_cache()
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="color:#94a3b8; font-size:0.8em; line-height:2;">
    <b>できること</b><br>
    📝 台本URLの提出<br>
    🔍 参考動画のリサーチ提出<br>
    ✅ ステータス更新<br>
    📝 備考の追記
    </div>
    """, unsafe_allow_html=True)

# ─── メイン ───────────────────────────────────────────────────────────────────

my_name = st.session_state["writer_name"].strip()
st.markdown("## ✏️ 台本作成者ページ")

if not my_name:
    st.info("👈 サイドバーにあなたの名前を入力してください。")
    st.stop()

st.markdown(f"### こんにちは、**{my_name}** さん 👋")
st.markdown("---")

# ─── タブ ────────────────────────────────────────────────────────────────────

tab_project, tab_reel, tab_research, tab_new = st.tabs(["📝 担当案件", "📱 担当リール", "🔍 リサーチ提出", "➕ 新規案件登録"])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: 担当案件
# ══════════════════════════════════════════════════════════════════════════════

with tab_project:
    df = load_data()

    if df.empty:
        st.warning("案件がまだ登録されていません。管理者に連絡してください。")
        st.stop()

    WRITER_VISIBLE = ["未着手", "台本作成中", "台本確認待ち"]
    df_w = df[df["ステータス"].isin(WRITER_VISIBLE)].copy()

    if not show_all:
        df_mine = df_w[df_w["担当台本作家"].astype(str).str.strip() == my_name]
    else:
        df_mine = df_w

    df_mine = df_mine.sort_values("納期", na_position="last").reset_index(drop=True)

    col_cnt = st.columns([3, 1])
    col_cnt[1].markdown(f"**担当案件: {len(df_mine)} 件**")

    if df_mine.empty:
        st.success("✨ 現在、対応が必要な台本案件はありません。お疲れ様です！")
    else:
        col_list, col_form = st.columns([2, 3], gap="large")

        with col_list:
            st.markdown("#### 📋 担当案件リスト")
            new_sel = render_project_cards(df_mine, st.session_state["writer_selected_id"])
            if new_sel != st.session_state["writer_selected_id"]:
                st.session_state["writer_selected_id"] = new_sel
                st.rerun()

        with col_form:
            sel_id = st.session_state["writer_selected_id"]

            if not sel_id:
                st.markdown("""
                <div style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;
                            padding:40px;text-align:center;color:#94a3b8;margin-top:40px;">
                    <div style="font-size:3em;">📝</div>
                    <div style="margin-top:12px;">左の案件カードを選択してください</div>
                </div>""", unsafe_allow_html=True)
            else:
                target = df_mine[df_mine["ID"].astype(str) == sel_id]
                if target.empty:
                    st.session_state["writer_selected_id"] = None
                    st.rerun()

                row = target.iloc[0]
                mgmt_no = str(row.get("管理番号", "") or "")
                no_str  = f"[{mgmt_no}] " if mgmt_no else ""

                st.markdown(f"#### 📝 {no_str}{row['案件名']}")
                ic = st.columns(3)
                ic[0].markdown(status_badge_html(str(row["ステータス"])), unsafe_allow_html=True)
                ic[1].markdown(f"**納期:** {days_label(row.get('納期'))}")
                ic[2].markdown(f"**編集者:** {row.get('担当編集者', '未定') or '未定'}")

                cur_url = str(row.get("台本URL", "") or "")
                if cur_url:
                    st.success(f"📄 台本URL提出済み: [開く]({cur_url})")

                st.markdown("---")

                with st.form(f"writer_form_{sel_id}"):
                    cur_status = str(row["ステータス"])
                    selectable = ["未着手"] + WRITER_STATUSES
                    new_status = st.radio(
                        "ステータス", selectable,
                        index=selectable.index(cur_status) if cur_status in selectable else 0,
                        format_func=lambda s: f"{STATUS_EMOJI.get(s, '')} {s}",
                        horizontal=True, label_visibility="collapsed",
                    )
                    new_url = st.text_input(
                        "📄 台本URL", value=cur_url,
                        placeholder="https://docs.google.com/document/d/...",
                    )
                    new_notes = st.text_area(
                        "備考・メモ", value=str(row.get("備考", "") or ""),
                        placeholder="修正点・確認事項など", height=100,
                    )
                    submitted = st.form_submit_button(
                        "📤 提出・更新する", use_container_width=True, type="primary"
                    )

                if submitted:
                    final_status = new_status
                    updates = {"ステータス": final_status, "台本URL": new_url, "備考": new_notes}
                    if new_url and new_url != cur_url:
                        # 新規提出時に台本提出日を自動スタンプ
                        updates["台本提出日"] = date.today().strftime("%Y/%m/%d")
                        if new_status == "台本作成中":
                            final_status = "台本確認待ち"
                            updates["ステータス"] = final_status
                            st.info("💡 台本URLが提出されたため、ステータスを「台本確認待ち」に自動変更しました。")
                    try:
                        update_row(str(row["ID"]), updates)
                        st.success(f"✅ 「{row['案件名']}」を更新しました！")
                        if final_status == "台本確認待ち":
                            st.balloons()
                    except Exception as e:
                        st.error(f"❌ 更新に失敗しました: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: 担当リール
# ══════════════════════════════════════════════════════════════════════════════

with tab_reel:
    df_r = load_reels()

    if df_r.empty:
        st.warning("リールがまだ登録されていません。管理者に連絡してください。")
    else:
        REEL_WRITER_VISIBLE = ["企画中", "台本作成中", "台本確認待ち"]
        df_rw = df_r[df_r["ステータス"].isin(REEL_WRITER_VISIBLE)].copy()

        if not show_all:
            df_reel_mine = df_rw[df_rw["担当台本作家"].astype(str).str.strip() == my_name]
        else:
            df_reel_mine = df_rw

        df_reel_mine = df_reel_mine.sort_values("投稿予定日", na_position="last").reset_index(drop=True)

        st.markdown(f"#### 📱 担当リール: **{len(df_reel_mine)} 件**")

        if df_reel_mine.empty:
            st.success("✨ 現在、台本作業が必要なリールはありません！お疲れ様です！")
        else:
            rc_list, rc_form = st.columns([2, 3], gap="large")

            with rc_list:
                st.markdown("#### 📋 担当リールリスト")
                new_reel_sel = render_reel_cards(df_reel_mine, st.session_state["reel_writer_selected_id"])
                if new_reel_sel != st.session_state["reel_writer_selected_id"]:
                    st.session_state["reel_writer_selected_id"] = new_reel_sel
                    st.rerun()

            with rc_form:
                sel_reel_id = st.session_state["reel_writer_selected_id"]

                if not sel_reel_id:
                    st.markdown("""
                    <div style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;
                                padding:40px;text-align:center;color:#94a3b8;margin-top:40px;">
                        <div style="font-size:3em;">📱</div>
                        <div style="margin-top:12px;">左のリールカードを選択してください</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    reel_target = df_reel_mine[df_reel_mine["ID"].astype(str) == sel_reel_id]
                    if reel_target.empty:
                        st.session_state["reel_writer_selected_id"] = None
                        st.rerun()

                    rrow = reel_target.iloc[0]
                    mgmt_no = str(rrow.get("管理番号", "") or "")
                    no_str  = f"[{mgmt_no}] " if mgmt_no else ""
                    plat    = str(rrow.get("プラットフォーム", ""))

                    st.markdown(f"#### 📱 {no_str}{rrow['タイトル']}")
                    ri1, ri2, ri3 = st.columns(3)
                    ri1.markdown(reel_status_badge_html(str(rrow["ステータス"])), unsafe_allow_html=True)
                    ri2.markdown(f"**投稿予定:** {days_label(rrow.get('投稿予定日'))}")
                    ri3.markdown(platform_badge_html(plat), unsafe_allow_html=True)

                    cur_reel_url = str(rrow.get("台本URL", "") or "")
                    if cur_reel_url:
                        st.success(f"📄 台本URL提出済み: [開く]({cur_reel_url})")

                    # キャプション・ハッシュタグの確認
                    cur_caption  = str(rrow.get("キャプション", "") or "")
                    cur_hashtags = str(rrow.get("ハッシュタグ", "") or "")
                    if cur_caption:
                        with st.expander("📝 現在のキャプション"):
                            st.text(cur_caption)
                    if cur_hashtags:
                        with st.expander("# 現在のハッシュタグ"):
                            st.text(cur_hashtags)

                    st.markdown("---")

                    with st.form(f"reel_writer_form_{sel_reel_id}"):
                        cur_reel_status = str(rrow["ステータス"])
                        selectable_r = ["企画中"] + REEL_WRITER_STATUSES
                        new_reel_status = st.radio(
                            "ステータス", selectable_r,
                            index=selectable_r.index(cur_reel_status) if cur_reel_status in selectable_r else 0,
                            format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s, '')} {s}",
                            horizontal=True, label_visibility="collapsed",
                        )
                        new_reel_script = st.text_input(
                            "📄 台本URL", value=cur_reel_url,
                            placeholder="https://docs.google.com/document/d/...",
                        )
                        new_reel_caption = st.text_area(
                            "📝 キャプション（下書き）", value=cur_caption,
                            height=100, placeholder="投稿本文のドラフトを入力...",
                        )
                        new_reel_hashtags = st.text_area(
                            "# ハッシュタグ", value=cur_hashtags,
                            height=60, placeholder="#タグ1 #タグ2 ...",
                        )
                        new_reel_notes = st.text_area(
                            "備考・メモ", value=str(rrow.get("備考", "") or ""),
                            placeholder="修正点・確認事項など", height=80,
                        )
                        r_submitted = st.form_submit_button(
                            "📤 提出・更新する", use_container_width=True, type="primary"
                        )

                    if r_submitted:
                        final_reel_status = new_reel_status
                        if new_reel_script and new_reel_script != cur_reel_url and new_reel_status == "台本作成中":
                            final_reel_status = "台本確認待ち"
                            st.info("💡 台本URLが提出されたため、ステータスを「台本確認待ち」に自動変更しました。")
                        try:
                            update_reel(str(rrow["ID"]), {
                                "ステータス":   final_reel_status,
                                "台本URL":      new_reel_script,
                                "キャプション": new_reel_caption,
                                "ハッシュタグ": new_reel_hashtags,
                                "備考":         new_reel_notes,
                            })
                            st.success(f"✅ 「{rrow['タイトル']}」を更新しました！")
                            if final_reel_status == "台本確認待ち":
                                st.balloons()
                        except Exception as e:
                            st.error(f"❌ 更新に失敗しました: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: リサーチ提出
# ══════════════════════════════════════════════════════════════════════════════

with tab_research:
    st.markdown("### 🔍 参考動画リサーチの提出")
    st.markdown("""
    <div style="background:#eff6ff;border-left:4px solid #3b82f6;
                padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
    参考にしたい動画のURLとポイントを提出してください。<br>
    管理者が確認し、<b>採用された動画が新しい案件として登録</b>されます。
    </div>
    """, unsafe_allow_html=True)

    # ── URL プレビューセクション（フォーム外でリアルタイム表示）─────────────

    st.markdown("#### 動画URLを入力してプレビュー確認")
    preview_url = st.text_input(
        "動画URL", value=st.session_state["research_preview_url"],
        placeholder="https://www.youtube.com/watch?v=...",
        key="preview_url_input",
    )
    st.session_state["research_preview_url"] = preview_url

    video_id = extract_youtube_id(preview_url)
    col_prev, col_info = st.columns([1, 2])

    with col_prev:
        if video_id:
            thumb_url = youtube_thumbnail(video_id, "mq")
            st.image(thumb_url, use_container_width=True)
            st.caption("🎬 YouTubeサムネイル")
        elif preview_url:
            st.markdown("""
            <div style="background:#f3f4f6;border-radius:8px;padding:20px;
                        text-align:center;color:#9ca3af;">
                <div style="font-size:2em;">🔗</div>
                <div style="font-size:0.85em;margin-top:8px;">YouTube以外のURL<br>（サムネイルなし）</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#f3f4f6;border-radius:8px;padding:20px;
                        text-align:center;color:#9ca3af;min-height:120px;">
                <div style="font-size:2em;padding-top:20px;">📹</div>
                <div style="font-size:0.85em;margin-top:8px;">URLを入力するとプレビューが表示されます</div>
            </div>""", unsafe_allow_html=True)

    with col_info:
        if video_id:
            st.success(f"✅ YouTube動画を認識しました（ID: `{video_id}`）")
        elif preview_url:
            st.info("🔗 YouTube以外のURL（サムネイルは表示されません）")

    st.markdown("---")

    # ── 提出フォーム ─────────────────────────────────────────────────────────

    with st.form("research_submit_form", clear_on_submit=True):
        st.markdown("#### 詳細情報を入力")

        f1, f2 = st.columns(2)
        with f1:
            form_title = st.text_input(
                "動画タイトル *",
                placeholder="例: 【月5万円】副業ランキングTOP5",
            )
        with f2:
            form_channel = st.text_input(
                "チャンネル名",
                placeholder="例: 〇〇チャンネル",
            )

        form_genre = st.selectbox("ジャンル", RESEARCH_GENRES)

        form_point = st.text_area(
            "参考にしたいポイント *",
            placeholder=(
                "例:\n"
                "・冒頭のフックが秀逸（最初の5秒で視聴者を引き込んでいる）\n"
                "・テロップのテンポと効果音の使い方が参考になる\n"
                "・構成がコンパクトで商品訴求がわかりやすい"
            ),
            height=150,
        )

        submitted_r = st.form_submit_button(
            "🔍 リサーチを提出する",
            use_container_width=True,
            type="primary",
        )

    if submitted_r:
        url_to_submit = st.session_state["research_preview_url"]
        if not form_title or not form_point:
            st.error("動画タイトルと参考ポイントは必須です。")
        elif not url_to_submit:
            st.error("動画URLを入力してください。")
        else:
            try:
                add_research({
                    "提出者":    my_name,
                    "動画タイトル": form_title,
                    "動画URL":   url_to_submit,
                    "チャンネル名": form_channel,
                    "参考ポイント": form_point,
                    "ジャンル":  form_genre,
                })
                st.success(f"✅ 「{form_title}」のリサーチを提出しました！管理者が確認します。")
                st.session_state["research_preview_url"] = ""
                st.balloons()
            except Exception as e:
                st.error(f"❌ 提出に失敗しました: {e}")

    # ── 自分の提出履歴 ────────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("#### 📋 あなたの提出履歴")

    df_r = load_research()
    if df_r.empty:
        st.info("まだリサーチの提出がありません。")
    else:
        my_research = df_r[df_r["提出者"].astype(str).str.strip() == my_name].copy()
        my_research = my_research.sort_values("提出日時", ascending=False).reset_index(drop=True)

        if my_research.empty:
            st.info("あなたの提出履歴はまだありません。")
        else:
            STATUS_ICON = {"未評価": "🟡", "採用": "✅", "不採用": "❌"}
            for _, r in my_research.iterrows():
                eval_status = str(r.get("評価ステータス", "未評価"))
                icon = STATUS_ICON.get(eval_status, "🟡")
                vid_id = extract_youtube_id(str(r.get("動画URL", "")))
                thumb = youtube_thumbnail(vid_id, "mq") if vid_id else None

                with st.container():
                    hc1, hc2 = st.columns([1, 4])
                    with hc1:
                        if thumb:
                            st.image(thumb, use_container_width=True)
                    with hc2:
                        submitted_at = r.get("提出日時")
                        date_str = submitted_at.strftime("%Y/%m/%d") if pd.notna(submitted_at) else "—"
                        st.markdown(
                            f"**{r.get('動画タイトル', '—')}**　"
                            f"{icon} `{eval_status}`　`{date_str}`"
                        )
                        st.caption(
                            f"チャンネル: {r.get('チャンネル名', '—')} ／ "
                            f"ジャンル: {r.get('ジャンル', '—')}"
                        )
                        if eval_status == "採用" and r.get("案件ID"):
                            st.success(f"🎉 案件化されました！ 案件ID: `{r['案件ID']}`")
                        elif eval_status == "不採用" and r.get("評価コメント"):
                            st.warning(f"コメント: {r['評価コメント']}")
                    st.markdown('<hr style="border-color:#f1f5f9;margin:8px 0;">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4: 新規案件登録
# ══════════════════════════════════════════════════════════════════════════════

with tab_new:
    st.markdown("### ➕ 新規案件を登録する")
    st.markdown("""
    <div style="background:#eff6ff;border-left:4px solid #3b82f6;
                padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;">
    新しい動画案件を直接登録できます。<br>
    あなたの名前は <b>担当台本作家</b> に自動で入力されます。
    </div>
    """, unsafe_allow_html=True)

    with st.form("writer_new_project_form", clear_on_submit=True):
        st.markdown("#### 基本情報")
        fn1, fn2, fn3 = st.columns(3)
        with fn1:
            fn_mgmt = st.text_input("管理番号", placeholder="例: 239")
        with fn2:
            fn_name = st.text_input("案件名 *", placeholder="例: 【商品紹介】〇〇リール")
        with fn3:
            fn_due = st.date_input("納期", min_value=date.today())

        fn4, fn5, fn6 = st.columns(3)
        with fn4:
            fn_status = st.selectbox(
                "初期ステータス", STATUSES,
                format_func=lambda s: f"{STATUS_EMOJI.get(s, '')} {s}",
            )
        with fn5:
            fn_writer = st.text_input("担当台本作家", value=my_name)
        with fn6:
            fn_editor = st.text_input("担当編集者", placeholder="例: 鈴木")

        fn_notes = st.text_area("備考", placeholder="特記事項があれば")

        fn_submitted = st.form_submit_button(
            "📝 案件を登録する", use_container_width=True, type="primary"
        )

    if fn_submitted:
        if not fn_name:
            st.error("案件名は必須です。")
        else:
            try:
                add_row({
                    "管理番号":    fn_mgmt,
                    "案件名":      fn_name,
                    "ステータス":  fn_status,
                    "担当台本作家": fn_writer,
                    "担当編集者":  fn_editor,
                    "納期":        fn_due.strftime("%Y/%m/%d"),
                    "備考":        fn_notes,
                })
                label = f"[{fn_mgmt}] " if fn_mgmt else ""
                st.success(f"✅ {label}「{fn_name}」を登録しました！")
                st.balloons()
                clear_cache()
            except Exception as e:
                st.error(f"❌ 登録に失敗しました: {e}")
