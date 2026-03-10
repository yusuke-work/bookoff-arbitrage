# ブックオフ → メルカリ 利益リサーチツール

ブックオフオンラインの商品を自動取得し、メルカリの売却済み相場と比較して
利益が出る商品だけをリストアップするツールです。

---

## 📂 プロジェクト構成

```text
bookoff-arbitrage/
├── extension/          # Chrome拡張機能 (フロントエンド)
│   ├── manifest.json
│   ├── content_script.js
│   ├── background.js
│   ├── popup.html
│   └── popup.js
└── backend/            # Pythonバックエンド (APIサーバー)
    ├── main.py         # FastAPI サーバー
    ├── mercari_scraper.py
    ├── spreadsheet.py
    └── requirements.txt
```

---

## 🚀 セットアップ手順

### 1. Pythonバックエンド (Windows環境)

パッケージ管理および仮想環境管理には非常に高速な `uv` を使用します。

**⚠️ 重要: 以下のすべてのコマンドは必ず `backend` フォルダに移動してから実行してください。**

```powershell
# バックエンドのディレクトリに移動
cd backend

# 仮想環境の作成 (uvを使用)
uv venv

# 依存パッケージのインストール
uv pip install -r requirements.txt

# Playwright（スクレイピング用）のブラウザをインストール
uv run playwright install chromium

# FastAPI サーバーの起動
uv run uvicorn main:app --reload --port 8000
# uv run python run.py
```

### 2. Googleスプレッドシート連携

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成します。
2. 「Google Sheets API」と「Google Drive API」を有効化します。
3. サービスアカウントを作成し、JSONキーをダウンロードします。
4. ダウンロードしたJSONを `backend/service_account.json` として配置します。
5. 出力先となる Google スプレッドシートを新規作成し、右上の「共有」から、サービスアカウントのメールアドレス（`xxx@xxx.iam.gserviceaccount.com`）に**編集者**権限を付与します。
6. `backend/spreadsheet.py` の `SPREADSHEET_ID` を、作成したスプレッドシートのID（URLの `/d/〇〇〇/edit` の〇〇〇部分）に変更します。


### 3. Chrome拡張機能のインストール

1. Chrome ブラウザで `chrome://extensions/` を開きます。
2. 右上の「デベロッパーモード」を **ON** にします。
3. 左上の「パッケージ化されていない拡張機能を読み込む」をクリックします。
4. プロジェクト内の `extension/` フォルダを選択して読み込ませます。

---

## 🎯 使い方

1. **サーバーの起動**: PowerShell等で `backend` ディレクトリへ移動し、APIサーバーを起動します。
   ```powershell
   cd backend
   uv run uvicorn main:app --port 8000
   ```
2. **ブックオフオンラインを開く**: ブラウザでリサーチしたい商品一覧ページを開きます。
   - 例: `https://shopping.bookoff.co.jp/search/keyword/ゲーム`
3. **拡張機能の実行**: アドレスバー右の拡張機能アイコン（パズルマーク）から本ツールをクリックします。
4. **条件設定**: 利益判定の閾値を設定します（デフォルト: 最新利益 500円以上、かつ利益率 30%以上）。
5. **調査開始**: 「▶ このページを調査する」ボタンをクリックします。
6. **結果確認**: ポップアップ内に結果が表示され、利益商品は自動でスプレッドシートに追記されます。

---

## 🧮 利益計算の仕組み

```text
純利益 = メルカリ相場中央値 - 仕入れ値 - メルカリ手数料(10%) - 送料
利益率 = (純利益 ÷ 仕入れ値) × 100
```

> **📦 送料の目安（自動計算）**
> - CD: 210円（ネコポス）
> - DVD / Blu-ray: 310円（宅急便コンパクト/ゆうパケットプラス等）
> - ゲーム: 210円（ネコポス）
> - その他（デフォルト）: 310円

※ メルカリ相場は「売り切れ商品の価格中央値」を使用します（最新最大20件に基づく）。

---

## 🔧 カスタマイズ

### 利益閾値の変更
拡張機能のポップアップ上部のフォームから変更できます。
もしデフォルトの初期値を変更したい場合は `extension/popup.js` を修正してください。
```javascript
minProfitInput.value = "500"  // 最低利益額（円）
minMarginInput.value = "30"   // 最低利益率（%）
```

### 送料目安の変更
`backend/main.py` の `SHIPPING_COST` 辞書を編集することで、各カテゴリの想定送料を変更できます。
```python
SHIPPING_COST = {
    "cd":   210,
    "dvd":  310,
    "game": 210,
    "default": 310,
}
```

### サイト構造変更時の対応（セレクタ修正）
ブックオフ側のWebサイトのデザインが変更された場合、商品が取得できなくなることがあります。
その際は `extension/content_script.js` にある `itemSelectors` と各要素のCSSセレクタを、最新のHTML構造に合わせて修正してください。
