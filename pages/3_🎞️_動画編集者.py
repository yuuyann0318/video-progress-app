"""
動画編集者ページ（タブ構成）

Tab 1 — 🎞️ 担当案件
  台本が上がってきた案件だけを見せて、素材URLを貼ってステータスを一発で更新できる

Tab 2 — 📱 担当リール
  リール編集タスクの管理・素材URL・完パケURL提出
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.config import (
    EDITOR_STATUSES, STATUS_EMOJI, STATUS_BG,
    REEL_STATUS_EMOJI, REEL_STATUS_BG, REEL_EDITOR_STATUSES,
    PLATFORM_EMOJI,
)
from utils.sheets import load_data, update_row, clear_cache
from utils.reels import load_reels, update_reel, clear_reel_cache, ensure_reel_headers
from utils.ui import (
    inject_css, render_project_cards, render_reel_cards,
    status_badge_html, reel_status_badge_html, platform_badge_html,
    days_label,
)

# ─── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="動画編集者 | 動画制作管理",
    page_icon="🎞️",
    layout="wide",
)
inject_css()
ensure_reel_headers()

# ─── セッション初期化 ──────────────────────────────────────────────────────────

if "editor_name"            not in st.session_state: st.session_state["editor_name"]            = ""
if "editor_selected_id"     not in st.session_state: st.session_state["editor_selected_id"]     = None
if "reel_editor_selected_id" not in st.session_state: st.session_state["reel_editor_selected_id"] = None

# ─── サイドバー ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎞️ 動画編集者")
    st.markdown("---")

    st.markdown("### あなたの名前")
    name_input = st.text_input(
        "名前",
        value=st.session_state["editor_name"],
        placeholder="例: 鈴木",
        label_visibility="collapsed",
    )
    if name_input != st.session_state["editor_name"]:
        st.session_state["editor_name"] = name_input
        st.session_state["editor_selected_id"] = None

    st.markdown("---")

    show_all = st.checkbox("全案件を表示（担当外も含む）", value=False)
    show_completed = st.checkbox("納品完了も表示", value=False)

    status_filter = st.multiselect(
        "ステータスで絞り込み",
        options=["台本確認待ち", "撮影中"] + EDITOR_STATUSES,
        format_func=lambda s: f"{STATUS_EMOJI.get(s, '')} {s}",
    )

    st.markdown("---")
    if st.button("🔄 データを最新化", use_container_width=True):
        clear_cache()
        clear_reel_cache()
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="color:#94a3b8; font-size:0.8em; line-height:1.8;">
    <b>動画編集者にできること</b><br>
    ✅ 素材フォルダURLの登録<br>
    ✅ 完パケ動画URLの提出<br>
    ✅ ステータスを納品完了へ更新<br>
    ✅ 備考の追記
    </div>
    """, unsafe_allow_html=True)

# ─── メインコンテンツ ──────────────────────────────────────────────────────────

my_name = st.session_state["editor_name"].strip()

st.markdown("## 🎞️ 動画編集者ページ")

if not my_name:
    st.info("👈 サイドバーにあなたの名前を入力してください。担当案件が表示されます。")
    st.markdown("---")
    df_all = load_data()
    if not df_all.empty:
        st.markdown("#### 現在登録されている案件")
        editors_list = sorted([e for e in df_all["担当編集者"].dropna().unique() if e])
        if editors_list:
            st.markdown("担当編集者: " + " / ".join([f"`{e}`" for e in editors_list]))
    st.stop()

st.markdown(f"### こんにちは、**{my_name}** さん 👋")
st.markdown("---")

# ─── タブ ────────────────────────────────────────────────────────────────────

tab_proj, tab_reel_edit = st.tabs(["🎞️ 担当案件", "📱 担当リール"])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: 担当案件
# ══════════════════════════════════════════════════════════════════════════════

with tab_proj:

    df = load_data()

    if df.empty:
        st.warning("案件がまだ登録されていません。管理者に連絡してください。")
    else:
        EDITOR_VISIBLE_STATUSES = ["台本確認待ち", "撮影中"] + EDITOR_STATUSES
        if show_completed:
            EDITOR_VISIBLE_STATUSES.append("納品完了")

        df_editor = df[df["ステータス"].isin(EDITOR_VISIBLE_STATUSES)].copy()

        if not show_all:
            df_mine = df_editor[df_editor["担当編集者"].astype(str).str.strip() == my_name]
        else:
            df_mine = df_editor

        if status_filter:
            df_mine = df_mine[df_mine["ステータス"].isin(status_filter)]

        df_mine = df_mine.sort_values("納期", na_position="last").reset_index(drop=True)

        st.markdown(f"**担当案件: {len(df_mine)} 件**")

        if df_mine.empty:
            st.success("✨ 現在、対応が必要な編集案件はありません。お疲れ様です！")
        else:
            col_list, col_form = st.columns([2, 3], gap="large")

            with col_list:
                st.markdown("#### 📋 担当案件リスト")
                st.caption("案件を選択して右側のフォームで更新できます")
                new_selected = render_project_cards(df_mine, st.session_state["editor_selected_id"])
                if new_selected != st.session_state["editor_selected_id"]:
                    st.session_state["editor_selected_id"] = new_selected
                    st.rerun()

            with col_form:
                selected_id = st.session_state["editor_selected_id"]

                if not selected_id:
                    st.markdown("#### ← 案件を選択してください")
                    st.markdown("""
                    <div style="background:#f8fafc;border:2px dashed #e2e8f0;
                        border-radius:12px;padding:40px;text-align:center;color:#94a3b8;">
                        <div style="font-size:3em;">🎞️</div>
                        <div style="margin-top:12px;">左の案件カードをクリックすると<br>更新フォームが表示されます</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    target = df_mine[df_mine["ID"].astype(str) == selected_id]
                    if target.empty:
                        st.session_state["editor_selected_id"] = None
                        st.rerun()
                    else:
                        row = target.iloc[0]
                        mgmt_no = str(row.get("管理番号", "") or "")
                        no_str  = f"[{mgmt_no}] " if mgmt_no else ""

                        st.markdown(f"#### 🎬 {no_str}{row['案件名']}")
                        info_cols = st.columns(3)
                        info_cols[0].markdown(status_badge_html(str(row["ステータス"])), unsafe_allow_html=True)
                        info_cols[1].markdown(f"**納期:** {days_label(row.get('納期'))}")
                        info_cols[2].markdown(f"**台本作家:** {row.get('担当台本作家', '未定') or '未定'}")

                        script_url = str(row.get("台本URL", "") or "")
                        if script_url:
                            st.info(f"📄 台本URL: [開く]({script_url})")
                        else:
                            st.warning("⚠️ 台本URLがまだ提出されていません。台本作家に確認してください。")

                        current_material = str(row.get("素材フォルダURL", "") or "")
                        current_final    = str(row.get("完パケ動画URL", "") or "")
                        if current_material:
                            st.success(f"📁 素材フォルダURL提出済み: [開く]({current_material})")
                        if current_final:
                            st.success(f"🎬 完パケ動画URL提出済み: [開く]({current_final})")

                        st.markdown("---")

                        with st.form(f"editor_form_{selected_id}"):
                            st.markdown("##### ステータスを更新")
                            current_status = str(row["ステータス"])
                            selectable = ["台本確認待ち", "撮影中"] + EDITOR_STATUSES
                            new_status = st.radio(
                                "ステータス", selectable,
                                index=selectable.index(current_status) if current_status in selectable else 0,
                                format_func=lambda s: f"{STATUS_EMOJI.get(s, '')} {s}",
                                horizontal=True, label_visibility="collapsed",
                            )
                            st.markdown("##### URLを提出・更新")
                            new_material_url = st.text_input("📁 素材フォルダURL", value=current_material,
                                placeholder="https://drive.google.com/drive/folders/...")
                            new_final_url = st.text_input("🎬 完パケ動画URL", value=current_final,
                                placeholder="https://drive.google.com/file/d/...")
                            new_notes = st.text_area("備考・メモ（追記）",
                                value=str(row.get("備考", "") or ""),
                                placeholder="修正対応内容・確認事項など", height=100)
                            submitted = st.form_submit_button("📤 提出・更新する",
                                use_container_width=True, type="primary")

                        if submitted:
                            final_status = new_status
                            edit_updates = {
                                "ステータス":     final_status,
                                "素材フォルダURL": new_material_url,
                                "完パケ動画URL":  new_final_url,
                                "備考":           new_notes,
                            }
                            if (new_final_url and new_final_url != current_final
                                    and new_status not in ["納品完了"]):
                                final_status = "納品完了"
                                edit_updates["ステータス"] = final_status
                                edit_updates["動画提出日"] = date.today().strftime("%Y/%m/%d")
                                st.info("💡 完パケ動画URLが提出されたため、ステータスを自動で「納品完了」に変更しました。")
                            try:
                                update_row(str(row["ID"]), edit_updates)
                                st.success(f"✅ 「{row['案件名']}」を更新しました！")
                                if final_status == "納品完了":
                                    st.balloons()
                                    st.markdown("### 🎉 納品完了！お疲れ様でした！")
                            except Exception as e:
                                st.error(f"❌ 更新に失敗しました: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: 担当リール編集
# ══════════════════════════════════════════════════════════════════════════════

with tab_reel_edit:
    df_reels = load_reels()

    if df_reels.empty:
        st.warning("リールがまだ登録されていません。管理者に連絡してください。")
    else:
        REEL_EDITOR_VISIBLE = ["台本確認待ち", "撮影待ち", "撮影中"] + REEL_EDITOR_STATUSES
        if show_completed:
            REEL_EDITOR_VISIBLE.append("投稿済み")

        df_re = df_reels[df_reels["ステータス"].isin(REEL_EDITOR_VISIBLE)].copy()

        if not show_all:
            df_reel_mine = df_re[df_re["担当編集者"].astype(str).str.strip() == my_name]
        else:
            df_reel_mine = df_re

        df_reel_mine = df_reel_mine.sort_values("投稿予定日", na_position="last").reset_index(drop=True)

        st.markdown(f"**担当リール: {len(df_reel_mine)} 件**")

        if df_reel_mine.empty:
            st.success("✨ 現在、対応が必要なリール編集案件はありません。お疲れ様です！")
        else:
            re_list, re_form = st.columns([2, 3], gap="large")

            with re_list:
                st.markdown("#### 📋 担当リールリスト")
                st.caption("リールを選択して右側のフォームで更新できます")
                new_re_sel = render_reel_cards(df_reel_mine, st.session_state["reel_editor_selected_id"])
                if new_re_sel != st.session_state["reel_editor_selected_id"]:
                    st.session_state["reel_editor_selected_id"] = new_re_sel
                    st.rerun()

            with re_form:
                sel_reel_id = st.session_state["reel_editor_selected_id"]

                if not sel_reel_id:
                    st.markdown("""
                    <div style="background:#f8fafc;border:2px dashed #e2e8f0;
                        border-radius:12px;padding:40px;text-align:center;color:#94a3b8;">
                        <div style="font-size:3em;">📱</div>
                        <div style="margin-top:12px;">左のリールカードをクリックすると<br>更新フォームが表示されます</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    reel_target = df_reel_mine[df_reel_mine["ID"].astype(str) == sel_reel_id]
                    if reel_target.empty:
                        st.session_state["reel_editor_selected_id"] = None
                        st.rerun()
                    else:
                        rrow = reel_target.iloc[0]
                        mgmt_no = str(rrow.get("管理番号", "") or "")
                        no_str  = f"[{mgmt_no}] " if mgmt_no else ""
                        plat    = str(rrow.get("プラットフォーム", ""))

                        st.markdown(f"#### 📱 {no_str}{rrow['タイトル']}")
                        ri1, ri2, ri3 = st.columns(3)
                        ri1.markdown(reel_status_badge_html(str(rrow["ステータス"])), unsafe_allow_html=True)
                        ri2.markdown(f"**投稿予定:** {days_label(rrow.get('投稿予定日'))}")
                        ri3.markdown(platform_badge_html(plat), unsafe_allow_html=True)

                        # 台本URL確認
                        reel_script = str(rrow.get("台本URL", "") or "")
                        if reel_script:
                            st.info(f"📄 台本URL: [開く]({reel_script})")
                        else:
                            st.warning("⚠️ 台本URLがまだ提出されていません。台本作家に確認してください。")

                        cur_reel_mat   = str(rrow.get("素材フォルダURL", "") or "")
                        cur_reel_final = str(rrow.get("完パケURL", "") or "")
                        if cur_reel_mat:
                            st.success(f"📁 素材フォルダURL提出済み: [開く]({cur_reel_mat})")
                        if cur_reel_final:
                            st.success(f"🎬 完パケURL提出済み: [開く]({cur_reel_final})")

                        st.markdown("---")

                        with st.form(f"reel_editor_form_{sel_reel_id}"):
                            cur_re_status = str(rrow["ステータス"])
                            re_selectable = ["台本確認待ち", "撮影待ち", "撮影中"] + REEL_EDITOR_STATUSES
                            new_re_status = st.radio(
                                "ステータス", re_selectable,
                                index=re_selectable.index(cur_re_status) if cur_re_status in re_selectable else 0,
                                format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s, '')} {s}",
                                horizontal=True, label_visibility="collapsed",
                            )
                            st.markdown("##### URLを提出・更新")
                            new_re_mat   = st.text_input("📁 素材フォルダURL", value=cur_reel_mat,
                                placeholder="https://drive.google.com/drive/folders/...")
                            new_re_final = st.text_input("🎬 完パケURL", value=cur_reel_final,
                                placeholder="https://drive.google.com/file/d/...")
                            new_re_notes = st.text_area("備考・メモ",
                                value=str(rrow.get("備考", "") or ""),
                                placeholder="修正点・確認事項など", height=80)
                            re_submitted = st.form_submit_button("📤 提出・更新する",
                                use_container_width=True, type="primary")

                        if re_submitted:
                            final_re_status = new_re_status
                            if (new_re_final and new_re_final != cur_reel_final
                                    and new_re_status not in ["投稿予定", "投稿済み"]):
                                final_re_status = "投稿予定"
                                st.info("💡 完パケURLが提出されたため、ステータスを「投稿予定」に自動変更しました。")
                            try:
                                update_reel(str(rrow["ID"]), {
                                    "ステータス":      final_re_status,
                                    "素材フォルダURL": new_re_mat,
                                    "完パケURL":       new_re_final,
                                    "備考":            new_re_notes,
                                })
                                st.success(f"✅ 「{rrow['タイトル']}」を更新しました！")
                                if final_re_status == "投稿予定":
                                    st.balloons()
                                    st.markdown("### 🎉 投稿準備完了！")
                            except Exception as e:
                                st.error(f"❌ 更新に失敗しました: {e}")
