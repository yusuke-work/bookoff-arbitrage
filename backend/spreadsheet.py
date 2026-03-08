# ============================================================
# spreadsheet.py
# 利益商品をGoogleスプレッドシートに追記する
# gspread ライブラリを使用
# ============================================================

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# ---- 設定 ----------------------------------------------------
# ここを自分の環境に合わせて変更してください

# サービスアカウントの認証情報JSONファイルのパス
SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "service_account.json"  # backend/ ディレクトリに置く
)

# スプレッドシートIDまたはURL
# 例: https://docs.google.com/spreadsheets/d/【ここ】/edit
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID",
    "YOUR_SPREADSHEET_ID_HERE"  # ← 自分のIDに変更
)

# 書き込み先シート名
SHEET_NAME = os.getenv("SHEET_NAME", "リサーチ結果")

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

    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"[SPREADSHEET] {len(rows)} 件を追記しました")
    return len(rows)


# ---- ヘルパー ------------------------------------------------

def _get_client() -> gspread.Client:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    return gspread.authorize(creds)


def _get_or_create_sheet(gc: gspread.Client) -> gspread.Worksheet:
    """シートが存在しない場合は作成してヘッダーを追加する"""
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    # シート名を探す
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        # シートを新規作成
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
        sheet.append_row(HEADERS)
        print(f"[SPREADSHEET] シート '{SHEET_NAME}' を新規作成しました")

    return sheet
