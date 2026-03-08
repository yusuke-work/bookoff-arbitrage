# ============================================================
# mercari_scraper.py
# Playwrightでメルカリの「売り切れ」商品の相場を取得する
# 中央値を返す
# ============================================================

import statistics
import time
import random
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---- 設定 ----------------------------------------------------

# 取得する売却済み商品の最大件数
MAX_ITEMS = 20

# ページ読み込みタイムアウト（ミリ秒）
TIMEOUT_MS = 15_000

# ---- メイン関数 ----------------------------------------------

def get_mercari_median_price(keyword: str) -> int | None:
    """
    メルカリで keyword を検索し、売却済み商品の価格中央値を返す。
    取得できなかった場合は None を返す。
    """
    prices = _scrape_sold_prices(keyword)
    if not prices:
        return None
    return int(statistics.median(prices))


def _scrape_sold_prices(keyword: str) -> list[int]:
    """売却済み商品の価格リストを返す"""
    prices = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # webdriver フラグを隠蔽
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            # メルカリ検索URL（売り切れのみ）
            encoded = keyword.replace(" ", "%20")
            url = (
                f"https://jp.mercari.com/search"
                f"?keyword={encoded}"
                f"&status=sold_out"         # 売り切れのみ
                f"&sort=created_time"       # 新着順
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
            browser.close()

    print(f"[MERCARI] '{keyword}' → {len(prices)}件取得, 中央値: {int(statistics.median(prices)) if prices else 'N/A'}")
    return prices


def _parse_price(text: str) -> int | None:
    """「¥1,234」→ 1234"""
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _human_wait(min_sec: float, max_sec: float):
    """人間らしいランダム待機"""
    time.sleep(min_sec + random.random() * (max_sec - min_sec))
