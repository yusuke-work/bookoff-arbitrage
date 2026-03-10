# ============================================================
# mercari_scraper.py
# Playwrightでメルカリの「売り切れ」商品の相場を取得する
#
# 設計:
#   - 専用スレッド（max_workers=1）の中でPlaywrightブラウザを保持する
#   - ブラウザは初回リクエスト時に1度だけ起動し、全商品で使い回す
#   - サーバー終了時に close() でクリーンアップする
#   - Windows の SelectorEventLoop 問題は、専用スレッド内で
#     WindowsProactorEventLoopPolicy を設定することで解決する
# ============================================================

import sys
import statistics
import os
import random
import re
import time
import urllib.parse
import asyncio
import concurrent.futures

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

# ---- 設定 ----------------------------------------------------

# 取得する売却済み商品の最大件数
MAX_ITEMS = 20

# ページ読み込みタイムアウト（ミリ秒）
TIMEOUT_MS = 15_000


# ---- 専用スレッドで動くPlaywrightワーカー --------------------

class _PlaywrightWorker:
    """
    単一の専用スレッド内でPlaywrightブラウザを保持・再利用するワーカー。
    すべてのメソッドは self._executor に送られ、同じスレッドで実行される。
    """

    def __init__(self):
        # 専用スレッド（max_workers=1 で同一スレッドを使い回す）
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        # 初期化は最初の検索時にスレッド内で行う
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._initialized = False

    def _init(self):
        """専用スレッド内でPlaywrightとブラウザを初期化する（初回のみ）"""
        if self._initialized:
            return

        # Windows では sync_playwright 内部のイベントループも ProactorLoop にする必要がある
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        print("[MERCARI] ブラウザを起動しています...")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--window-size=1280,800",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._initialized = True
        print("[MERCARI] ブラウザの起動が完了しました")

    def scrape(self, keyword: str) -> list[int]:
        """専用スレッド内でメルカリを検索して価格リストを返す"""
        self._init()

        prices = []
        page: Page | None = None
        try:
            page = self._context.new_page()

            # メルカリ検索URL（売り切れのみ）
            encoded = urllib.parse.quote(keyword)
            url = (
                f"https://jp.mercari.com/search"
                f"?keyword={encoded}"
                f"&status=sold_out"
                f"&sort=created_time"
                f"&order=desc"
            )

            page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
            _human_wait(1.5, 3.0)



            # 商品カードが読み込まれるまで待機
            try:
                page.wait_for_selector("li[data-testid='item-cell']", timeout=TIMEOUT_MS)
            except PlaywrightTimeout:
                print(f"[MERCARI] 商品が見つかりません: {keyword}")
                return []

            # デバッグ用 スクリーンショット保存
            safe_keyword = re.sub(r'[\\/:*?"<>|]', '_', keyword)
            os.makedirs("screenshots", exist_ok=True)
            screenshot_path = f"screenshots/debug_{safe_keyword}.png"
            page.screenshot(path=screenshot_path)
            print(f"[MERCARI_DEBUG] スクリーンショットを保存しました: {screenshot_path}")

            # 価格テキストを取得
            items = page.query_selector_all("li[data-testid='item-cell']")
            for item in items[:MAX_ITEMS]:
                price_el = item.query_selector("[class*='price']")
                if price_el:
                    text = price_el.inner_text()
                    price = _parse_price(text)
                    if price and price > 0:
                        prices.append(price)

        except Exception as e:
            print(f"[MERCARI ERROR] {keyword}: {e}")
        finally:
            if page:
                page.close()

        print(f"[MERCARI] '{keyword}' → {len(prices)}件取得, 中央値: {int(statistics.median(prices)) if prices else 'N/A'}")
        return prices

    def shutdown(self):
        """専用スレッド内でブラウザリソースをクリーンアップする"""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._initialized = False
        print("[MERCARI] ブラウザを終了しました")


# ---- MercariScraper（asyncio側のインターフェース） ----------

class MercariScraper:
    def __init__(self):
        self._worker = _PlaywrightWorker()
        self._lock = asyncio.Lock()

    async def get_median_price(self, keyword: str) -> int | None:
        """指定キーワードのメルカリ相場（中央値）を取得する"""
        async with self._lock:
            prices = await asyncio.get_event_loop().run_in_executor(
                self._worker._executor,
                self._worker.scrape,
                keyword,
            )
        if not prices:
            return None
        return int(statistics.median(prices))

    async def close(self):
        """サーバー終了時にブラウザをシャットダウンする"""
        await asyncio.get_event_loop().run_in_executor(
            self._worker._executor,
            self._worker.shutdown,
        )
        self._worker._executor.shutdown(wait=True)


# ---- ユーティリティ ------------------------------------------

def _parse_price(text: str) -> int | None:
    """「¥1,234」→ 1234"""
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _human_wait(min_sec: float, max_sec: float):
    """人間らしいランダム待機（同期）"""
    time.sleep(min_sec + random.random() * (max_sec - min_sec))


# グローバルなスクレイパーインスタンスを作成
_scraper_instance = MercariScraper()

# 下位互換用
async def get_mercari_median_price(keyword: str) -> int | None:
    return await _scraper_instance.get_median_price(keyword)
