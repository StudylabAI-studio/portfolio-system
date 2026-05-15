# ポートフォリオ評価システム — 基本プラン v1.0

## 概要

教育現場向けの**AIポートフォリオ自動評価システム**。  
生徒のライフログCSVをアップロードするだけで、Gemini AIがルーブリックに基づいて評価し、美しいPDFレポートを一括生成する。

---

## システム構成

```
portfolio_system/
├── app.py               # Streamlit メイン画面（Step 1〜3）
├── ai_evaluator.py      # Gemini API 評価エンジン
├── pdf_builder.py       # PDF生成（Jinja2 + Playwright）
├── radar_chart.py       # レーダーチャート生成（matplotlib）
├── prompt_builder.py    # プロンプト補助
├── requirements.txt     # 依存パッケージ
├── start.bat            # ワンクリック起動
├── .env                 # APIキー（Git管理外）
└── templates/           # HTMLテンプレート（6種）
    ├── type_a.html      # 青グラデーション・スタンダード
    ├── type_b.html      # 賞状風・ゴールド
    ├── type_c.html      # ダークダッシュボード
    ├── premium_a.html   # プレミアム・宇宙ネイビー
    ├── premium_b.html   # プレミアム・アクリル
    └── premium_c.html   # プレミアム・シルバー
```

---

## 機能一覧

### Step 1: データ入力
- ライフログCSV（姓・名・ユーザーID・テーマ・内容・投稿日時）を読み込み
- ルーブリック（CSV / Excel / PDF / TXT）を読み込み
- 生徒ごとに自動グループ化・件数集計

### Step 2: AI自動評価
- **モデル**: Gemini 3.1 Flash Lite（選択可能）
- **評価項目**: ルーブリックから自動抽出 or 固定5項目
- **出力内容**:
  - 各項目スコア（1.0〜5.0、0.1刻み）
  - 各項目の根拠コメント（200文字以上・ログ引用付き・人間味のある表現）
  - 総合コメント（400文字・今後のアドバイス入り）
- 評価結果CSVのダウンロード機能付き

### Step 3: PDF一括生成
- 6種類のテンプレートから選択
- 法人名・ロゴ（透かし or 右上）をカスタマイズ可能
- Playwright でHTMLをA4PDFに変換
- 全生徒分をZIPで一括ダウンロード

---

## 表示の特徴

| 要素 | 仕様 |
|---|---|
| 星評価 | CSS部分塗りで端数を正確に表現（例：2.3点 → ★★☆☆☆ の3割塗り） |
| レーダーチャート | 日本語フォント対応・透過度15%・グリッド目盛り表示 |
| 根拠コメント | 各評価項目200文字以上・ログ引用必須 |
| 総合フィードバック | 400文字・今後のアドバイス2〜3点付き |
| レイアウト | A4サイズ・余白に応じて自動拡張 |

---

## 技術スタック

| 分類 | 内容 |
|---|---|
| LLM | Google Gemini API (`google-genai` SDK) |
| UI | Streamlit |
| PDF生成 | Playwright (Chromium) + Jinja2 |
| チャート | matplotlib (polar chart) |
| フォント | Noto Sans JP (Web) / Yu Gothic/Meiryo (チャート) |
| 環境 | Python 3.11+, venv |

---

## 起動方法

```
start.bat をダブルクリック
→ http://localhost:8502 が開く
```

---

## Git管理情報

| ブランチ | 用途 |
|---|---|
| `master` | 本番リリース版（タグで管理） |
| `develop` | 機能追加・開発用 |

| タグ | 内容 |
|---|---|
| `v1.0-basic-plan` | 基本プラン完成版（2026-05-15） |

### v1.0 に戻す方法
```bash
git checkout v1.0-basic-plan
```

---

## 既知の制限（v1.0時点）

- ルーブリック項目が多い場合、PDF1枚に収まりきらないことがある
- 生徒数が多い場合（30名以上）、AI評価に時間がかかる
- インターネット接続が必要（Gemini API / Googleフォント）
