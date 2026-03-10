# ============================================================
# spreadsheet.py
# 利益商品をGoogleスプレッドシートに追記する
# gspread ライブラリを使用
# ============================================================

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import time
from dotenv import load_dotenv

# ---- 設定 ----------------------------------------------------
# ここを自分の環境に合わせて変更してください
load_dotenv()

# サービスアカウントの認証情報JSONファイルのパス
SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "service_account.json"  # backend/ ディレクトリに置く
)

# スプレッドシートIDまたはURL
# 例: https://docs.google.com/spreadsheets/d/【ここ】/edit
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise ValueError("環境変数 'SPREADSHEET_ID' が設定されていません。")

# 書き込み先シート名
SHEET_NAME = os.getenv("SHEET_NAME", "リサーチ結果")

# グローバルキャッシュされたクライアント
_cached_client = None

# ---- ヘッダー定義 --------------------------------------------
HEADERS = [
    "調査日時",
    "商品名",
    "仕入れ値（円）",
    "メルカリ相場中央値（円）",
    "手数料+送料（円）",
    "純利益（円）",
    "利益率（%）",
    "ブックオフURL",
]

# ---- メイン関数 ----------------------------------------------

def append_profitable_items(items: list[dict]) -> int:
    """
    利益商品リストをスプレッドシートに追記する。
    追記した行数を返す。
    """
    if not items:
        return 0

    gc = _get_client()
    sheet = _get_or_create_sheet(gc)

    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
    rows = []

    for item in items:
        rows.append([
            now_str,
            item.get("title", ""),
            item.get("buy_price", 0),
            item.get("median_price", 0),
            item.get("fees", 0),
            item.get("profit", 0),
            item.get("margin", 0),
            item.get("url", ""),
        ])

    max_retries = 3
    for attempt in range(max_retries):
        try:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"[SPREADSHEET] {len(rows)} 件を追記しました")
            print(f"[SPREADSHEET] 処理終了")
            return len(rows)
        except Exception as e:
            print(f"[SPREADSHEET ERROR] 書き込みに失敗しました (試行 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
            else:
                print("[SPREADSHEET ERROR] 最大再試行回数に達しました。書き込みをスキップします。")
                return 0
    return 0


# ---- ヘルパー ------------------------------------------------

def _get_client() -> gspread.Client:
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    _cached_client = gspread.authorize(creds)
    return _cached_client


def _get_or_create_sheet(gc: gspread.Client) -> gspread.Worksheet:
    """シートが存在しない場合は作成してヘッダーを追加する"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)

            # シート名を探す
            try:
                sheet = spreadsheet.worksheet(SHEET_NAME)
            except gspread.exceptions.WorksheetNotFound:
                # シートを新規作成
                sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
                sheet.append_row(HEADERS)
                print(f"[SPREADSHEET] シート '{SHEET_NAME}' を新規作成しました")

            return sheet
        except Exception as e:
            print(f"[SPREADSHEET ERROR] シートの取得/作成に失敗しました (試行 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
