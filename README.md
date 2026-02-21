# 動画制作 × SNS投稿 管理システム

Streamlit + Google Sheets による動画制作・SNS投稿の一元管理ツール。

---

## 起動方法

```bash
/Users/yuuya/Library/Python/3.9/bin/streamlit run app.py
```

アクセス: http://localhost:8501

---

## ページ構成

| ページ | 役割 |
|--------|------|
| `app.py` | ホーム（役割選択カード + クイックKPI） |
| `pages/1_📊_管理者.py` | 案件ダッシュボード + リサーチ評価 |
| `pages/2_✏️_台本作成者.py` | 担当案件 / 担当リール / リサーチ提出 |
| `pages/3_🎞️_動画編集者.py` | 担当案件 / 担当リール（素材・完パケ提出） |
| `pages/4_📱_リール管理.py` | リール全管理（ダッシュボード/一覧/新規登録/分析） |
| `pages/5_📅_カレンダー.py` | 月別カレンダー + 今週スケジュール + アラート |

---

## Google Sheets 構成

| シート名 | 用途 |
|----------|------|
| `VideoProjects` | 動画案件（台本・編集・納品管理） |
| `ResearchItems` | リサーチ提出 |
| `ReelPosts` | インスタリール / SNS投稿管理 |

---

## ファイル構成

```
video-progress-app/
├── app.py                      # ホームページ
├── credentials.json            # Google Service Account 認証情報
├── README.md                   # このファイル
├── pages/
│   ├── 1_📊_管理者.py
│   ├── 2_✏️_台本作成者.py
│   ├── 3_🎞️_動画編集者.py
│   ├── 4_📱_リール管理.py
│   └── 5_📅_カレンダー.py
└── utils/
    ├── config.py               # 定数定義（ステータス・色・カラム名）
    ├── sheets.py               # VideoProjects CRUD
    ├── reels.py                # ReelPosts CRUD
    ├── research.py             # ResearchItems CRUD
    └── ui.py                   # 共通UIコンポーネント
```

---

## 主な機能

### リール管理 (page 4)
- KPIダッシュボード（再生数・いいね・保存数など）
- ステータスパイプライン管理（企画中 → 投稿済み）
- 検索・フィルター・ページネーション付き一覧
- パフォーマンス分析（TOP10・月別・プラットフォーム比較）

### カレンダー (page 5)
- 月別カレンダービュー（前月・翌月ナビゲーション）
- VideoProjects の納期 + ReelPosts の投稿予定を統合表示
- アラート機能（今日の投稿・明日の投稿・期限超過・3日以内締め切り）

---

## 技術スタック

- Python 3.9
- Streamlit
- gspread + google-auth（Google Sheets API）
- pandas
