"""
インスタリール / SNS投稿 管理ページ（管理者用）

Tab 1 — 📊 ダッシュボード
  KPI / 今週の投稿予定 / パイプラインファネル / 直近アラート

Tab 2 — 📋 リール一覧
  検索・フィルター・ページネーション・行選択編集

Tab 3 — ➕ 新規登録
  リール案件の新規登録フォーム

Tab 4 — 📈 パフォーマンス分析
  投稿済みリールのアナリティクス集計・ランキング
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
from datetime import date, timedelta

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.config import (
    REEL_STATUSES, REEL_STATUS_EMOJI, REEL_STATUS_BG, REEL_STATUS_TEXT,
    REEL_WRITER_STATUSES, REEL_EDITOR_STATUSES,
    PLATFORMS, PLATFORM_EMOJI, PLATFORM_COLOR,
    CONTENT_TYPES, REEL_ANALYTICS_COLS,
)
from utils.reels import load_reels, add_reel, update_reel, clear_reel_cache, ensure_reel_headers
from utils.ui import inject_css, reel_status_badge_html, platform_badge_html, days_label, paginate

# ─── ページ設定 ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="リール管理 | 動画制作管理",
    page_icon="📱",
    layout="wide",
)
inject_css()
ensure_reel_headers()

# ─── セッション初期化 ──────────────────────────────────────────────────────────

for k, v in {
    "reel_selected_id": None,
    "reel_edit_mode":   False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── サイドバー ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📱 リール管理")
    st.markdown("---")

    st.markdown("### 🔍 検索")
    search_q = st.text_input(
        "タイトル / 管理番号 / 担当者",
        placeholder="例: R-001、田中、PR",
        label_visibility="collapsed",
    )

    st.markdown("### 📋 フィルター")
    status_filter = st.multiselect(
        "ステータス", options=REEL_STATUSES,
        format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s,'')} {s}",
    )
    platform_filter = st.multiselect(
        "プラットフォーム", options=PLATFORMS,
        format_func=lambda p: f"{PLATFORM_EMOJI.get(p,'')} {p}",
    )
    content_filter = st.multiselect("コンテンツ種別", options=CONTENT_TYPES)

    st.markdown("### 🔃 並び順")
    sort_key = st.selectbox(
        "並び順",
        ["投稿予定日が近い順", "最終更新が新しい順", "管理番号順", "タイトル順"],
        label_visibility="collapsed",
    )
    hide_archived = st.checkbox("📦 アーカイブを非表示", value=True)
    hide_posted   = st.checkbox("✅ 投稿済みを非表示",   value=False)

    st.markdown("---")
    if st.button("🔄 データを最新化", use_container_width=True):
        clear_reel_cache()
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="color:#94a3b8; font-size:0.78em; line-height:1.9;">
    <b>📱 ステータスフロー</b><br>
    💡 企画中<br>
    ✏️ 台本作成中<br>
    🔍 台本確認待ち<br>
    📸 撮影待ち<br>
    🎥 撮影中<br>
    🎞️ 編集中<br>
    👀 レビュー中<br>
    📅 投稿予定<br>
    ✅ 投稿済み
    </div>
    """, unsafe_allow_html=True)


# ─── ヘルパー ──────────────────────────────────────────────────────────────────

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if search_q:
        q = search_q.lower()
        mask = (
            df["タイトル"].astype(str).str.lower().str.contains(q) |
            df["管理番号"].astype(str).str.lower().str.contains(q) |
            df["担当台本作家"].astype(str).str.lower().str.contains(q) |
            df["担当編集者"].astype(str).str.lower().str.contains(q)
        )
        df = df[mask]
    if status_filter:
        df = df[df["ステータス"].isin(status_filter)]
    if platform_filter:
        df = df[df["プラットフォーム"].isin(platform_filter)]
    if content_filter:
        df = df[df["コンテンツ種別"].isin(content_filter)]
    if hide_archived:
        df = df[df["ステータス"] != "アーカイブ"]
    if hide_posted:
        df = df[df["ステータス"] != "投稿済み"]
    return df


def apply_sort(df: pd.DataFrame) -> pd.DataFrame:
    if sort_key == "投稿予定日が近い順":
        return df.sort_values("投稿予定日", na_position="last")
    elif sort_key == "最終更新が新しい順":
        return df.sort_values("最終更新日時", ascending=False)
    elif sort_key == "管理番号順":
        return df.sort_values("管理番号")
    else:
        return df.sort_values("タイトル")


# ─── メイン ───────────────────────────────────────────────────────────────────

st.markdown("## 📱 インスタリール / SNS投稿管理")

tab_dash, tab_list, tab_new, tab_analytics = st.tabs([
    "📊 ダッシュボード",
    "📋 リール一覧",
    "➕ 新規登録",
    "📈 パフォーマンス分析",
])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1: ダッシュボード
# ══════════════════════════════════════════════════════════════════════════════

with tab_dash:
    df_all = load_reels()
    today  = pd.Timestamp(date.today())

    # ── KPI ────────────────────────────────────────────────────────────────
    total      = len(df_all[df_all["ステータス"] != "アーカイブ"])
    posted     = len(df_all[df_all["ステータス"] == "投稿済み"])
    pipeline   = total - posted
    this_week  = df_all[
        (df_all["投稿予定日"].notna()) &
        (df_all["投稿予定日"] >= today) &
        (df_all["投稿予定日"] <= today + pd.Timedelta(days=7)) &
        (df_all["ステータス"] != "投稿済み")
    ]
    today_start = today
    today_end   = today + pd.Timedelta(days=1)
    today_posts = df_all[
        (df_all["投稿予定日"].notna()) &
        (df_all["投稿予定日"] >= today_start) &
        (df_all["投稿予定日"] <  today_end) &
        (df_all["ステータス"].isin(["投稿予定", "投稿済み"]))
    ]

    st.markdown("### 📊 KPIサマリー")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📁 総リール数",    total)
    k2.metric("🔄 制作パイプライン", pipeline)
    k3.metric("✅ 投稿済み",       posted)
    k4.metric("📅 今週の投稿予定", len(this_week))
    k5.metric("🔴 本日の投稿",    len(today_posts))

    st.markdown("---")

    col_funnel, col_upcoming = st.columns([1, 1], gap="large")

    # ── パイプラインファネル ────────────────────────────────────────────────
    with col_funnel:
        st.markdown("#### 🔄 ステータス別パイプライン")
        status_counts = df_all[df_all["ステータス"] != "アーカイブ"]["ステータス"].value_counts()
        for st_name in REEL_STATUSES:
            if st_name == "アーカイブ":
                continue
            count = status_counts.get(st_name, 0)
            if count == 0:
                continue
            emoji = REEL_STATUS_EMOJI.get(st_name, "")
            bg    = REEL_STATUS_BG.get(st_name, "#f3f4f6")
            color = REEL_STATUS_TEXT.get(st_name, "#374151")
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

    # ── 今週の投稿予定 ──────────────────────────────────────────────────────
    with col_upcoming:
        st.markdown("#### 📅 今後7日間の投稿予定")
        if this_week.empty:
            st.markdown("""
            <div style="background:#f8fafc;border:2px dashed #e2e8f0;border-radius:12px;
                        padding:30px;text-align:center;color:#94a3b8;">
                <div style="font-size:2.5em;">🎉</div>
                <div style="margin-top:8px;">今週の投稿予定はありません</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            tw_sorted = this_week.sort_values("投稿予定日")
            for _, row in tw_sorted.iterrows():
                due = row.get("投稿予定日")
                due_str = due.strftime("%m/%d(%a)") if pd.notna(due) else "—"
                plat = str(row.get("プラットフォーム", ""))
                plat_c = PLATFORM_COLOR.get(plat, "#7c3aed")
                plat_e = PLATFORM_EMOJI.get(plat, "📲")
                status = str(row.get("ステータス", ""))
                st_bg  = REEL_STATUS_BG.get(status, "#f3f4f6")
                st_e   = REEL_STATUS_EMOJI.get(status, "")
                title  = str(row.get("タイトル", ""))[:25]
                mgmt   = str(row.get("管理番号", ""))
                no_str = f"[{mgmt}] " if mgmt else ""
                st.markdown(
                    f'<div style="background:{st_bg};border-radius:10px;padding:10px 14px;'
                    f'margin-bottom:7px;border-left:4px solid {plat_c};">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<b style="font-size:0.9em;">{no_str}{title}</b>'
                    f'<span style="background:{plat_c};color:white;padding:2px 8px;'
                    f'border-radius:999px;font-size:0.75em;font-weight:700;">'
                    f'{plat_e} {plat}</span>'
                    f'</div>'
                    f'<div style="margin-top:4px;font-size:0.8em;color:#64748b;">'
                    f'📅 {due_str} &nbsp; {st_e} {status}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── プラットフォーム別内訳 ──────────────────────────────────────────────
    st.markdown("#### 📊 プラットフォーム別投稿数")
    df_active = df_all[df_all["ステータス"].isin(["投稿済み"])]
    if not df_active.empty:
        plat_counts = df_active["プラットフォーム"].value_counts()
        p_cols = st.columns(len(plat_counts))
        for i, (plat, cnt) in enumerate(plat_counts.items()):
            color = PLATFORM_COLOR.get(str(plat), "#7c3aed")
            emoji = PLATFORM_EMOJI.get(str(plat), "📲")
            p_cols[i].markdown(
                f'<div style="background:white;border:2px solid {color};border-radius:12px;'
                f'padding:16px;text-align:center;">'
                f'<div style="font-size:2em;">{emoji}</div>'
                f'<div style="font-size:1.6em;font-weight:800;color:{color};">{cnt}</div>'
                f'<div style="font-size:0.8em;color:#64748b;">{plat}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("📊 投稿済みのリールがまだありません。")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2: リール一覧
# ══════════════════════════════════════════════════════════════════════════════

with tab_list:
    df = load_reels()
    filtered_df = apply_sort(apply_filters(df))

    st.markdown(f"### 📋 リール一覧　`{len(filtered_df)}` 件")

    if filtered_df.empty:
        st.info("該当するリールがありません。フィルターを調整してください。")
    else:
        # 表示用DataFrame
        disp = filtered_df.copy()
        disp["投稿予定"] = disp["投稿予定日"].apply(lambda x: x.strftime("%Y/%m/%d") if pd.notna(x) else "—")
        disp["残り"] = disp["投稿予定日"].apply(days_label)
        disp["ST"] = disp["ステータス"].apply(
            lambda s: f"{REEL_STATUS_EMOJI.get(s,'')} {s}"
        )
        disp["PF"] = disp["プラットフォーム"].apply(
            lambda p: f"{PLATFORM_EMOJI.get(p,'')} {p}"
        )

        show_cols = {
            "管理番号":     "管理番号",
            "タイトル":     "タイトル",
            "ST":           "ステータス",
            "PF":           "プラットフォーム",
            "コンテンツ種別": "種別",
            "担当台本作家": "台本作家",
            "担当編集者":  "編集者",
            "投稿予定":    "投稿予定日",
            "残り":        "残り",
        }
        render_cols = [c for c in show_cols if c in disp.columns]
        render_df = disp[render_cols].rename(columns=show_cols)

        def _reel_row_style(row):
            raw = row.get("ステータス", "")
            status = next((s for s in REEL_STATUS_BG if s in raw), "")
            if status == "投稿済み":
                return ["color:#94a3b8; font-style:italic"] * len(row)
            bg = REEL_STATUS_BG.get(status, "")
            return [f"background-color:{bg}"] * len(row)

        styled = render_df.style.apply(_reel_row_style, axis=1)

        paged_df = paginate(filtered_df, key="reel_list")

        pdisp = paged_df.copy()
        pdisp["投稿予定"] = pdisp["投稿予定日"].dt.strftime("%Y/%m/%d").fillna("—")
        pdisp["残り"] = pdisp["投稿予定日"].apply(days_label)
        pdisp["ST"] = pdisp["ステータス"].apply(
            lambda s: f"{REEL_STATUS_EMOJI.get(s,'')} {s}"
        )
        pdisp["PF"] = pdisp["プラットフォーム"].apply(
            lambda p: f"{PLATFORM_EMOJI.get(p,'')} {p}"
        )
        prender_df = pdisp[render_cols].rename(columns=show_cols)
        pstyled = prender_df.style.apply(_reel_row_style, axis=1)

        event = st.dataframe(
            pstyled,
            use_container_width=True,
            hide_index=True,
            height=min(48 * len(prender_df) + 48, 600),
            on_select="rerun",
            selection_mode="single-row",
            key="reel_table_df",
        )

        selected_rows = event.selection.rows
        selected_reel = pd.DataFrame()
        if selected_rows:
            selected_reel = paged_df.iloc[[selected_rows[0]]]

        # ── 選択行の編集フォーム ────────────────────────────────────────────
        if not selected_reel.empty:
            row    = selected_reel.iloc[0]
            row_id = str(row["ID"])

            st.markdown("---")
            st.markdown(
                f"### ✏️ 編集: **{row['タイトル']}** &nbsp; "
                + reel_status_badge_html(str(row["ステータス"]))
                + " &nbsp; " + platform_badge_html(str(row.get("プラットフォーム", ""))),
                unsafe_allow_html=True,
            )

            with st.form(f"reel_edit_form_{row_id}"):
                st.markdown("#### 📝 基本情報")
                e1, e2, e3 = st.columns(3)
                with e1:
                    new_mgmt   = st.text_input("管理番号", value=str(row.get("管理番号", "") or ""))
                with e2:
                    new_title  = st.text_input("タイトル", value=str(row.get("タイトル", "") or ""))
                with e3:
                    new_status = st.selectbox(
                        "ステータス", REEL_STATUSES,
                        index=REEL_STATUSES.index(row["ステータス"]) if row["ステータス"] in REEL_STATUSES else 0,
                        format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s,'')} {s}",
                    )

                e4, e5, e6 = st.columns(3)
                with e4:
                    new_platform = st.selectbox(
                        "プラットフォーム", PLATFORMS,
                        index=PLATFORMS.index(row.get("プラットフォーム")) if row.get("プラットフォーム") in PLATFORMS else 0,
                        format_func=lambda p: f"{PLATFORM_EMOJI.get(p,'')} {p}",
                    )
                with e5:
                    new_content = st.selectbox(
                        "コンテンツ種別", CONTENT_TYPES,
                        index=CONTENT_TYPES.index(row.get("コンテンツ種別")) if row.get("コンテンツ種別") in CONTENT_TYPES else 0,
                    )
                with e6:
                    new_series = st.text_input("シリーズ名", value=str(row.get("シリーズ名", "") or ""))

                e7, e8 = st.columns(2)
                with e7:
                    new_writer = st.text_input("担当台本作家", value=str(row.get("担当台本作家", "") or ""))
                with e8:
                    new_editor = st.text_input("担当編集者",   value=str(row.get("担当編集者", "") or ""))

                st.markdown("#### 📅 スケジュール")
                s1, s2, s3 = st.columns(3)
                with s1:
                    sched_val  = row.get("投稿予定日")
                    sched_def  = sched_val.date() if pd.notna(sched_val) and hasattr(sched_val, "date") else date.today()
                    new_sched  = st.date_input("投稿予定日", value=sched_def)
                with s2:
                    new_time   = st.text_input("投稿時間 (HH:MM)", value=str(row.get("投稿時間", "") or ""), placeholder="例: 19:00")
                with s3:
                    posted_val = row.get("投稿済み日")
                    posted_def = posted_val.date() if pd.notna(posted_val) and hasattr(posted_val, "date") else None
                    new_posted = st.date_input("投稿済み日（任意）", value=posted_def)

                st.markdown("#### 🔗 URL")
                u1, u2 = st.columns(2)
                with u1:
                    new_script   = st.text_input("台本URL",       value=str(row.get("台本URL", "") or ""))
                    new_material = st.text_input("素材フォルダURL", value=str(row.get("素材フォルダURL", "") or ""))
                with u2:
                    new_final    = st.text_input("完パケURL",      value=str(row.get("完パケURL", "") or ""))
                    new_post_url = st.text_input("投稿URL（投稿済み後）", value=str(row.get("投稿URL", "") or ""))

                st.markdown("#### 📝 Instagram投稿内容")
                new_caption = st.text_area(
                    "キャプション", value=str(row.get("キャプション", "") or ""),
                    height=120, placeholder="投稿本文を入力...",
                )
                new_hashtags = st.text_area(
                    "ハッシュタグ", value=str(row.get("ハッシュタグ", "") or ""),
                    height=80, placeholder="#インスタグラム #リール ...",
                )
                new_music = st.text_input(
                    "音楽・BGM", value=str(row.get("音楽・BGM", "") or ""),
                    placeholder="例: オリジナル楽曲 / Trending Audio",
                )

                st.markdown("#### 📊 アナリティクス（投稿後に入力）")
                ac1, ac2, ac3, ac4, ac5 = st.columns(5)
                def _int_val(r, col):
                    v = r.get(col, 0)
                    try:
                        return int(float(str(v))) if str(v) not in ["", "nan", "None"] else 0
                    except:
                        return 0
                with ac1: new_views    = st.number_input("再生数",   value=_int_val(row, "再生数"),   min_value=0, step=100)
                with ac2: new_likes    = st.number_input("いいね数", value=_int_val(row, "いいね数"), min_value=0, step=10)
                with ac3: new_saves    = st.number_input("保存数",   value=_int_val(row, "保存数"),   min_value=0, step=10)
                with ac4: new_comments = st.number_input("コメント数", value=_int_val(row, "コメント数"), min_value=0, step=1)
                with ac5: new_reach    = st.number_input("リーチ数", value=_int_val(row, "リーチ数"),  min_value=0, step=100)

                new_notes = st.text_area("備考", value=str(row.get("備考", "") or ""))

                btn_update = st.form_submit_button("💾 更新する", use_container_width=True, type="primary")

            if btn_update:
                try:
                    posted_str = new_posted.strftime("%Y/%m/%d") if new_posted else ""
                    update_reel(row_id, {
                        "管理番号": new_mgmt, "タイトル": new_title, "ステータス": new_status,
                        "プラットフォーム": new_platform, "コンテンツ種別": new_content,
                        "シリーズ名": new_series,
                        "担当台本作家": new_writer, "担当編集者": new_editor,
                        "投稿予定日": new_sched.strftime("%Y/%m/%d"),
                        "投稿時間": new_time, "投稿済み日": posted_str,
                        "台本URL": new_script, "素材フォルダURL": new_material,
                        "完パケURL": new_final, "投稿URL": new_post_url,
                        "キャプション": new_caption, "ハッシュタグ": new_hashtags,
                        "音楽・BGM": new_music,
                        "再生数": str(new_views), "いいね数": str(new_likes),
                        "保存数": str(new_saves), "コメント数": str(new_comments),
                        "リーチ数": str(new_reach),
                        "備考": new_notes,
                    })
                    st.success(f"✅ 「{new_title}」を更新しました！")
                    if new_status == "投稿済み":
                        st.balloons()
                        st.markdown("### 🎉 投稿完了！お疲れ様でした！")
                except Exception as e:
                    st.error(f"❌ 更新に失敗しました: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3: 新規登録
# ══════════════════════════════════════════════════════════════════════════════

with tab_new:
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
        with n1: n_mgmt     = st.text_input("管理番号 *",  placeholder="例: R-001")
        with n2: n_title    = st.text_input("タイトル *",  placeholder="例: 【PR】〇〇商品紹介リール")
        with n3: n_status   = st.selectbox(
            "初期ステータス", REEL_STATUSES,
            format_func=lambda s: f"{REEL_STATUS_EMOJI.get(s,'')} {s}",
        )

        n4, n5, n6 = st.columns(3)
        with n4: n_platform = st.selectbox(
            "プラットフォーム *", PLATFORMS,
            format_func=lambda p: f"{PLATFORM_EMOJI.get(p,'')} {p}",
        )
        with n5: n_content  = st.selectbox("コンテンツ種別", CONTENT_TYPES)
        with n6: n_series   = st.text_input("シリーズ名",    placeholder="例: 週1回商品紹介シリーズ")

        st.markdown("#### 👥 担当者")
        t1, t2 = st.columns(2)
        with t1: n_writer = st.text_input("担当台本作家", placeholder="例: 田中")
        with t2: n_editor = st.text_input("担当編集者",  placeholder="例: 鈴木")

        st.markdown("#### 📅 スケジュール")
        d1, d2 = st.columns(2)
        with d1: n_sched = st.date_input("投稿予定日 *", value=date.today() + timedelta(days=7))
        with d2: n_time  = st.text_input("投稿時間 (HH:MM)", placeholder="例: 19:00 (Instagramは夜7-9時が高エンゲージメント)")

        st.markdown("#### 📝 Instagram投稿内容（任意・後から編集可）")
        n_caption  = st.text_area("キャプション", height=100, placeholder="投稿本文のドラフト...")
        n_hashtags = st.text_area("ハッシュタグ",  height=60,  placeholder="#タグ1 #タグ2 ...")
        n_music    = st.text_input("音楽・BGM", placeholder="例: オリジナル音声 / Trending Audio名")

        st.markdown("#### 🔗 URL（任意・後から追加可）")
        u1, u2 = st.columns(2)
        with u1:
            n_script   = st.text_input("台本URL",       placeholder="Google Docs URL...")
            n_material = st.text_input("素材フォルダURL", placeholder="Google Drive URL...")
        with u2:
            n_final    = st.text_input("完パケURL",      placeholder="Google Drive URL...")
            n_post_url = st.text_input("投稿URL",        placeholder="Instagram投稿URL...")

        n_notes = st.text_area("備考", placeholder="特記事項・クライアント要望など")

        btn_register = st.form_submit_button("📱 リールを登録する", use_container_width=True, type="primary")

    if btn_register:
        if not n_mgmt or not n_title:
            st.error("⚠️ 管理番号とタイトルは必須です。")
        else:
            try:
                reel_id = add_reel({
                    "管理番号": n_mgmt, "タイトル": n_title, "ステータス": n_status,
                    "プラットフォーム": n_platform, "コンテンツ種別": n_content,
                    "シリーズ名": n_series,
                    "担当台本作家": n_writer, "担当編集者": n_editor,
                    "投稿予定日": n_sched.strftime("%Y/%m/%d"), "投稿時間": n_time,
                    "台本URL": n_script, "素材フォルダURL": n_material,
                    "完パケURL": n_final, "投稿URL": n_post_url,
                    "キャプション": n_caption, "ハッシュタグ": n_hashtags,
                    "音楽・BGM": n_music, "備考": n_notes,
                })
                st.success(f"🎉 管理番号 [{n_mgmt}]「{n_title}」を登録しました！（ID: `{reel_id}`）")
                st.balloons()
            except Exception as e:
                st.error(f"❌ 登録に失敗しました: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4: パフォーマンス分析
# ══════════════════════════════════════════════════════════════════════════════

with tab_analytics:
    df_analytics = load_reels()
    df_posted = df_analytics[
        (df_analytics["ステータス"] == "投稿済み") &
        (df_analytics["再生数"] > 0)
    ].copy()

    st.markdown("### 📈 パフォーマンス分析")

    if df_posted.empty:
        st.info("📊 アナリティクスデータがまだありません。\n\n投稿済みリールにアナリティクスを入力してください（リール一覧タブから編集できます）。")
    else:
        # ── 総合KPI ────────────────────────────────────────────────────────
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
        ak1.metric("📱 投稿数",      total_posts)
        ak2.metric("▶️ 総再生数",    f"{total_views:,}")
        ak3.metric("❤️ 総いいね数",  f"{total_likes:,}")
        ak4.metric("🔖 総保存数",    f"{total_saves:,}")
        ak5.metric("📊 平均再生数",  f"{avg_views:,}")
        ak6.metric("💫 平均エンゲージ率", f"{avg_engagement}%")

        st.markdown("---")

        col_top, col_chart = st.columns([1, 1], gap="large")

        # ── Top 10 リール ──────────────────────────────────────────────────
        with col_top:
            st.markdown("#### 🥇 再生数ランキング TOP 10")
            top10 = df_posted.nlargest(10, "再生数")[
                ["管理番号", "タイトル", "プラットフォーム", "再生数", "いいね数", "保存数"]
            ].reset_index(drop=True)

            for i, row in top10.iterrows():
                rank_color = ["#FFD700", "#C0C0C0", "#CD7F32"] + ["#94a3b8"] * 7
                medal = ["🥇", "🥈", "🥉"] + [f"{i+1}" for i in range(3, 10)]
                plat = str(row.get("プラットフォーム", ""))
                plat_c = PLATFORM_COLOR.get(plat, "#7c3aed")
                plat_e = PLATFORM_EMOJI.get(plat, "📲")
                title  = str(row.get("タイトル", ""))[:20]
                views  = int(row.get("再生数", 0))
                likes  = int(row.get("いいね数", 0))
                saves  = int(row.get("保存数", 0))
                st.markdown(
                    f'<div style="display:flex;align-items:center;padding:8px 12px;'
                    f'border-radius:8px;margin-bottom:5px;background:#f8fafc;">'
                    f'<span style="font-size:1.3em;width:36px;">{medal[i]}</span>'
                    f'<div style="flex:1;">'
                    f'<b style="font-size:0.88em;">{title}</b><br>'
                    f'<span style="font-size:0.75em;color:#64748b;">'
                    f'{plat_e} {plat} &nbsp;|&nbsp; ▶️ {views:,} &nbsp; ❤️ {likes:,} &nbsp; 🔖 {saves:,}'
                    f'</span></div></div>',
                    unsafe_allow_html=True,
                )

        # ── 月別投稿数チャート ────────────────────────────────────────────
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
            for _, row in top_save.iterrows():
                title = str(row.get("タイトル", ""))[:18]
                rate  = float(row.get("保存率", 0))
                views = int(row.get("再生数", 0))
                bar_w = min(int(rate * 10), 100)
                st.markdown(
                    f'<div style="margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:0.8em;margin-bottom:2px;">'
                    f'<span>{title}</span><span style="font-weight:700;">{rate}%</span></div>'
                    f'<div style="background:#f1f5f9;border-radius:999px;height:10px;">'
                    f'<div style="width:{bar_w}%;background:#e1306c;height:100%;border-radius:999px;"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # ── プラットフォーム別比較 ────────────────────────────────────────
        st.markdown("#### 📊 プラットフォーム別 平均パフォーマンス比較")
        plat_perf = df_posted.groupby("プラットフォーム")[REEL_ANALYTICS_COLS].mean().round(0).astype(int)
        if not plat_perf.empty:
            plat_perf.columns = ["平均再生数", "平均いいね", "平均保存", "平均コメント", "平均リーチ"]
            st.dataframe(plat_perf, use_container_width=True)
