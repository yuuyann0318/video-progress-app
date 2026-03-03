"""
シンプルなパスワード認証ユーティリティ

- EDIT_PASSWORD が Secrets に設定されていれば認証必須
- 未設定の場合はローカル開発用として常に編集可能
- session_state["authenticated"] で状態を管理
"""

import streamlit as st


def render_auth_sidebar() -> bool:
    """
    サイドバーに認証UIを描画し、認証状態を返す。

    Returns:
        bool: 編集可能かどうか
    """
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # Secretsにパスワードが未設定の場合は常に編集可能（ローカル開発）
    correct_pwd = st.secrets.get("EDIT_PASSWORD", "")
    if not correct_pwd:
        return True

    with st.sidebar:
        st.markdown("---")
        if st.session_state["authenticated"]:
            st.success("✅ 編集モード")
            if st.button("🔒 ログアウト", use_container_width=True, key="auth_logout"):
                st.session_state["authenticated"] = False
                st.rerun()
        else:
            st.markdown("### 🔐 編集ログイン")
            pwd = st.text_input(
                "パスワード",
                type="password",
                key="auth_password_input",
                placeholder="パスワードを入力",
            )
            if st.button("ログイン", use_container_width=True, key="auth_login"):
                if pwd and pwd == correct_pwd:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("パスワードが違います")
            st.caption("※ 閲覧は認証不要です")

    return st.session_state["authenticated"]


def is_authenticated() -> bool:
    """現在の認証状態を返す（UIなし）"""
    correct_pwd = st.secrets.get("EDIT_PASSWORD", "")
    if not correct_pwd:
        return True  # パスワード未設定 = ローカル開発モード
    return st.session_state.get("authenticated", False)
