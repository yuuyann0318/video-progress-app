"""
credentials.json → .streamlit/secrets.toml 自動生成スクリプト

使い方:
    python3 make_secrets.py

実行すると .streamlit/secrets.toml が生成されます。
ローカル開発用です。このファイルはGitHubに上がりません（.gitignore で除外済み）。
"""

import json
import os

CREDS_PATH   = os.path.join(os.path.dirname(__file__), "credentials.json")
SECRETS_PATH = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")

def main():
    if not os.path.exists(CREDS_PATH):
        print(f"❌ {CREDS_PATH} が見つかりません。")
        return

    with open(CREDS_PATH, encoding="utf-8") as f:
        creds = json.load(f)

    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)

    lines = ["[gcp_service_account]"]
    for key, val in creds.items():
        if isinstance(val, str):
            # private_key の改行を \\n に変換
            escaped = val.replace("\\n", "\n").replace("\n", "\\n")
            lines.append(f'{key} = "{escaped}"')
        else:
            lines.append(f'{key} = "{val}"')

    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✅ {SECRETS_PATH} を生成しました！")
    print("   これで st.secrets['gcp_service_account'] から認証情報を読めます。")

if __name__ == "__main__":
    main()
