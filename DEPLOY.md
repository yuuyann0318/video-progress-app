# 🚀 Streamlit Community Cloud デプロイガイド

誰でも・どこからでもアクセスできるURLが**無料**で手に入ります。

---

## ⏱ 所要時間：約15〜20分（初回のみ）

---

## ステップ1：GitHubリポジトリを作る

1. [github.com](https://github.com) にログイン（アカウントがなければ無料登録）
2. 右上の「＋」→「New repository」をクリック
3. 設定:
   - Repository name: `video-progress-app`（任意）
   - **Private**（非公開）を選択 ← 重要！
   - 「Create repository」をクリック

---

## ステップ2：コードをGitHubにアップロード

ターミナルで以下を実行：

```bash
# video-progress-appフォルダに移動
cd /Users/yuuya/video-progress-app

# Gitを初期化（初回のみ）
git init
git add .
git commit -m "初回コミット"

# GitHubリポジトリに接続してpush
# ※ GitHubで表示されるURLに置き換えること
git remote add origin https://github.com/あなたのユーザー名/video-progress-app.git
git branch -M main
git push -u origin main
```

> ⚠️ `.gitignore` に `credentials.json` が含まれているため、
> 認証情報は**絶対にGitHubに上がりません**（安全です）。

---

## ステップ3：Streamlit Community Cloudにデプロイ

1. [share.streamlit.io](https://share.streamlit.io) にアクセス
2. 「Sign in with GitHub」でログイン
3. 「New app」をクリック
4. 設定:
   - **Repository**: `あなたのユーザー名/video-progress-app`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. 「Deploy!」をクリック

---

## ステップ4：Secretsを設定する（最重要）

デプロイ後、Google Sheetsに接続するために認証情報を登録します。

### 4-1. credentials.jsonの内容を確認

```bash
cat /Users/yuuya/video-progress-app/credentials.json
```

### 4-2. Streamlit Cloud の Secrets 画面を開く

- デプロイしたアプリの右側「⋮」→「Settings」→「Secrets」タブ

### 4-3. 以下の形式で貼り付ける

```toml
[gcp_service_account]
type                        = "service_account"
project_id                  = "credentials.jsonのproject_idの値"
private_key_id              = "credentials.jsonのprivate_key_idの値"
private_key                 = "credentials.jsonのprivate_keyの値（そのまま）"
client_email                = "credentials.jsonのclient_emailの値"
client_id                   = "credentials.jsonのclient_idの値"
auth_uri                    = "https://accounts.google.com/o/oauth2/auth"
token_uri                   = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url        = "credentials.jsonのclient_x509_cert_urlの値"
universe_domain             = "googleapis.com"
```

> 💡 **ワンコマンド変換**（手動コピペを省略）:
> ```bash
> cd /Users/yuuya/video-progress-app
> python3 make_secrets.py
> cat .streamlit/secrets.toml
> ```
> 出力された内容をそのままStreamlitのSecrets画面に貼り付ければOK！

### 4-4. 「Save」して完了

アプリが自動的に再起動し、Google Sheetsに接続されます。

---

## 完了！

`https://あなたのアプリ名.streamlit.app` のURLが発行されます。
このURLをチームに共有すれば、スマホ・PC問わずどこからでもアクセスできます！

---

## よくある質問

**Q: 無料でずっと使える？**
A: はい。Streamlit Community Cloudは完全無料で、制限なし（1アプリ/GitHubアカウント）。

**Q: データはどこに保存されるの？**
A: 変わらずGoogleスプレッドシートです。アプリはデータを持ちません。

**Q: コードを更新したらどうする？**
A: `git push` するだけで自動デプロイされます。

**Q: アクセス制限（パスワード）はかけられる？**
A: Streamlit Cloud の設定で「Viewers must be logged in」にするか、
   コード内に簡易パスワード認証を追加できます（必要なら対応可）。
