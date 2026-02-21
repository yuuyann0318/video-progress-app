"""
ステップ1: Google Sheets 接続テストスクリプト
実行方法: python test_connection.py
"""

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import sys
import os

SPREADSHEET_ID = "1RlV-mj83pKmeOe4DkfpllAJxvs6g0R7VUPMPZXAOzoU"
SHEET_NAME = "VideoProjects"
CREDENTIALS_PATH = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "ID", "案件名", "ステータス", "担当台本作家", "担当編集者",
    "納期", "台本URL", "素材フォルダURL", "完パケ動画URL", "備考", "最終更新日時"
]


def test_connection():
    print("=" * 50)
    print("  Google Sheets 接続テスト")
    print("=" * 50)

    # --- credentials.json の確認 ---
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"\n❌ credentials.json が見つかりません")
        print(f"   配置場所: {os.path.abspath(CREDENTIALS_PATH)}")
        print("\n📋 取得手順:")
        print("   1. https://console.cloud.google.com/ にアクセス")
        print("   2. プロジェクトを作成（または既存を選択）")
        print("   3. 「APIとサービス」→「ライブラリ」で以下を有効化:")
        print("      - Google Sheets API")
        print("      - Google Drive API")
        print("   4. 「APIとサービス」→「認証情報」→「サービスアカウント」を作成")
        print("   5. 作成したサービスアカウントのJSONキーをダウンロード")
        print(f"   6. このフォルダに 'credentials.json' という名前で配置")
        print(f"      配置先: {os.path.abspath('.')}")
        print("\n⚠️  重要: スプレッドシートをサービスアカウントのメールアドレスと共有してください")
        sys.exit(1)

    print(f"\n✅ credentials.json を発見")

    # --- 認証 ---
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(creds)
        print("✅ 認証成功")
    except Exception as e:
        print(f"\n❌ 認証エラー: {e}")
        sys.exit(1)

    # --- スプレッドシート接続 ---
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print(f"✅ スプレッドシートに接続: 「{spreadsheet.title}」")
    except gspread.exceptions.APIError as e:
        print(f"\n❌ スプレッドシートへのアクセスエラー: {e}")
        print("⚠️  サービスアカウントのメールアドレスをスプレッドシートの共有設定に追加してください")
        print(f"   メールアドレスは credentials.json 内の 'client_email' の値です")
        sys.exit(1)

    # --- シートの確認 / 作成 ---
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
        print(f"✅ シート「{SHEET_NAME}」を発見")
    except gspread.WorksheetNotFound:
        print(f"⚠️  シート「{SHEET_NAME}」が存在しないため作成します...")
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=20)
        sheet.append_row(HEADERS)
        print(f"✅ シート「{SHEET_NAME}」を作成し、ヘッダーを設定しました")

    # --- データ取得テスト ---
    try:
        records = sheet.get_all_records()
        print(f"✅ データ取得成功: {len(records)} 件の案件")

        if records:
            df = pd.DataFrame(records)
            print("\n--- データプレビュー ---")
            print(df.to_string(index=False))
        else:
            print("   （まだデータがありません。新規登録画面から追加できます）")
    except Exception as e:
        print(f"\n❌ データ取得エラー: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  🎉 接続テスト完了！アプリを起動できます")
    print("  実行コマンド: streamlit run app.py")
    print("=" * 50)


if __name__ == "__main__":
    test_connection()
