"""
接続テスト・診断ページ
デプロイ確認 & Secrets の状態を確認する
"""
import streamlit as st

st.set_page_config(page_title="接続テスト", page_icon="🔧")
st.title("🔧 接続テスト・診断")
st.caption("このページはデバッグ用です。問題が解決したら削除します。")

# ── デプロイバージョン確認 ─────────────────────────────────────────────────────
st.subheader("1. デプロイ確認")
st.success("✅ このメッセージが見えていれば、最新コードがデプロイされています（v3）")

# ── Secrets の状態確認 ────────────────────────────────────────────────────────
st.subheader("2. Secrets の状態")

try:
    top_keys = list(st.secrets.keys())
    st.write(f"**Secretsのトップレベルキー:** `{top_keys}`")

    if not top_keys:
        st.error("❌ Secrets が空です。Streamlit Cloud の Secrets に何も設定されていません。")
    elif "gcp_service_account" in st.secrets:
        sub_keys = list(st.secrets["gcp_service_account"].keys())
        st.success(f"✅ `[gcp_service_account]` セクションが見つかりました！")
        st.write(f"**含まれているキー:** `{sub_keys}`")
        if "private_key" in sub_keys:
            pk = st.secrets["gcp_service_account"]["private_key"]
            st.write(f"**private_key の先頭20文字:** `{pk[:20]}...`")
            st.write(f"**private_key に改行が含まれているか:** `{'\\n' in pk}`")
        else:
            st.error("❌ private_key がありません！")
    elif "GOOGLE_CREDENTIALS_B64" in st.secrets:
        st.success("✅ `GOOGLE_CREDENTIALS_B64` キーが見つかりました（Base64方式）")
    else:
        st.error(f"❌ `gcp_service_account` も `GOOGLE_CREDENTIALS_B64` もありません。")
        st.write("**見つかったキー:**", top_keys)

except Exception as e:
    st.error(f"❌ Secrets へのアクセス中にエラー: {e}")

# ── Google Sheets 接続テスト ───────────────────────────────────────────────────
st.subheader("3. Google Sheets 接続テスト")

if st.button("接続テスト実行"):
    try:
        from google.oauth2.service_account import Credentials
        import gspread
        import json, base64
        from utils.config import SCOPES, SPREADSHEET_ID, SHEET_NAME, CREDENTIALS_PATH

        # 認証取得
        creds = None
        auth_method = None

        if "GOOGLE_CREDENTIALS_B64" in st.secrets:
            raw = base64.b64decode(st.secrets["GOOGLE_CREDENTIALS_B64"]).decode()
            info = json.loads(raw)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            auth_method = "Base64"
        elif "gcp_service_account" in st.secrets:
            info = {k: v for k, v in st.secrets["gcp_service_account"].items()}
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            auth_method = "gcp_service_account"
        else:
            import os
            creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
            auth_method = "credentials.json（ローカル）"

        st.info(f"認証方法: {auth_method}")

        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(SHEET_NAME)
        rows = sheet.get_all_values()
        st.success(f"✅ Google Sheets 接続成功！ {len(rows)} 行取得しました。")

    except FileNotFoundError as e:
        st.error(f"❌ credentials.jsonが見つかりません: {e}")
    except Exception as e:
        st.error(f"❌ エラー: {type(e).__name__}: {e}")
