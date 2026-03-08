# ブックオフ → メルカリ 利益リサーチツール

ブックオフオンラインの商品を自動取得し、メルカリの売却済み相場と比較して
利益が出る商品だけをリストアップするツールです。

---

## 構成

```
bookoff-arbitrage/
├── extension/          # Chrome拡張機能
│   ├── manifest.json
│   ├── content_script.js
│   ├── background.js
│   ├── popup.html
│   └── popup.js
└── backend/            # Pythonバックエンド
    ├── main.py         # FastAPI サーバー
    ├── mercari_scraper.py
    ├── spreadsheet.py
    └── requirements.txt
```

---

## セットアップ

### 1. Pythonバックエンド (Windows環境)

```powershell
cd backend

# 仮想環境の作成 (uvを使用)
uv venv

# 依存パッケージのインストール
uv pip install -r requirements.txt

# Playwrightのブラウザをインストール
uv run playwright install chromium

# サーバー起動
uv run uvicorn main:app --reload --port 8000
```

### 2. Googleスプレッドシート連携

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「Google Sheets API」と「Google Drive API」を有効化
3. サービスアカウントを作成し、JSONキーをダウンロード
4. ダウンロードしたJSONを `backend/service_account.json` として配置
5. 対象のスプレッドシートをサービスアカウントのメールアドレスに共有
6. `backend/spreadsheet.py` の `SPREADSHEET_ID` を自分のIDに変更

または環境変数で設定 (PowerShellの場合)：
```powershell
$env:GOOGLE_SERVICE_ACCOUNT_JSON="path\to\service_account.json"
$env:SPREADSHEET_ID="your_spreadsheet_id"
$env:SHEET_NAME="リサーチ結果"
```

### 3. Chrome拡張機能のインストール

1. Chrome で `chrome://extensions/` を開く
2. 右上の「デベロッパーモード」をON
3. 「パッケージ化されていない拡張機能を読み込む」をクリック
4. `extension/` フォルダを選択

---

## 使い方

1. Pythonバックエンドを起動しておく（`uv run uvicorn main:app --port 8000`）
2. ブックオフオンラインの商品一覧ページを開く
   - 例: `https://shopping.bookoff.co.jp/search/keyword/ゲーム`
3. Chrome拡張機能のアイコンをクリック
4. 利益判定の閾値を設定（デフォルト: 利益500円以上 かつ 利益率30%以上）
5. 「▶ このページを調査する」ボタンをクリック
6. 結果が表示され、利益商品はスプレッドシートにも自動追記される

---

## 利益計算の仕組み

```
純利益 = メルカリ相場中央値 - 仕入れ値 - メルカリ手数料(10%) - 送料
利益率 = 純利益 ÷ 仕入れ値 × 100

※ 送料の目安
  CD:   210円（ネコポス）
  DVD:  310円（宅急便コンパクト）
  ゲーム: 210円（ネコポス）
```

メルカリ相場は「売り切れ商品の価格中央値」を使用します（最大20件）。

---

## カスタマイズ

### 利益閾値の変更
拡張機能のポップアップ上部のフォームから変更できます。
コードで固定したい場合は `popup.js` の初期値を変更：
```js
minProfitInput.value = "500"  // 最低利益額（円）
minMarginInput.value = "30"   // 最低利益率（%）
```

### 送料の変更
`main.py` の `SHIPPING_COST` を編集：
```python
SHIPPING_COST = {
    "cd":   210,
    "dvd":  310,
    "game": 210,
    "default": 310,
}
```

### ブックオフの商品カードセレクタが変わった場合
`content_script.js` の `itemSelectors` と各要素のセレクタを修正してください。
