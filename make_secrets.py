"""
credentials.json → .streamlit/secrets.toml 自動生成スクリプト

使い方:
    python3 make_secrets.py
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
        if key == "private_key":
            # private_key はトリプルクォートで囲む（改行をそのまま扱える）
            # 前後の改行を trim してから triple-quote で包む
            lines.append(key + ' = """' + val + '"""')
        elif isinstance(val, str):
            # 通常の文字列: ダブルクォートをエスケープ
            escaped = val.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(key + ' = "' + escaped + '"')
        else:
            lines.append(key + ' = "' + str(val) + '"')

    content = "\n".join(lines) + "\n"

    with open(SECRETS_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ .streamlit/secrets.toml を生成しました！\n")
    print("── 以下をStreamlit CloudのSecretsにコピーしてください ──\n")
    print(content)
    print("────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
