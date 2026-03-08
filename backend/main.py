# ============================================================
# main.py
# FastAPI バックエンド
# Chrome拡張機能から商品リストを受け取り、メルカリ相場調査を行う
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
import asyncio

from backend.mercari_scraper import get_mercari_median_price
from backend.spreadsheet import append_profitable_items

app = FastAPI(title="ブックオフせどりリサーチAPI")

# Chrome拡張機能からのリクエストを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 利益計算の定数 ------------------------------------------

# メルカリ販売手数料
MERCARI_FEE_RATE = 0.10

# カテゴリ別送料（らくらくメルカリ便、ネコポス/宅急便コンパクト基準）
# ※ 実際の送料は重量・サイズで変わるため、カテゴリ別の想定値を使用
SHIPPING_COST = {
    "cd":   210,
    "dvd":  310,
    "game": 210,
    "default": 310,
}

# ---- ジョブ管理（インメモリ）---------------------------------
# { job_id: { "products": [...], "results": [...], "done": int, "finished": bool } }
jobs: dict = {}

# ---- スキーマ ------------------------------------------------

class Product(BaseModel):
    title: str
    price: int       # ブックオフでの仕入れ価格（円）
    url: str
    imageUrl: Optional[str] = ""

class ResearchRequest(BaseModel):
    products: List[Product]

# ---- エンドポイント ------------------------------------------

@app.post("/research")
async def start_research(req: ResearchRequest):
    """調査ジョブを開始して job_id を返す"""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "products": [p.dict() for p in req.products],
        "results": [],
        "done": 0,
        "finished": False,
    }
    # バックグラウンドで調査を実行
    asyncio.create_task(run_research(job_id))
    return {"job_id": job_id, "total": len(req.products)}


@app.get("/status/{job_id}")
async def get_status(job_id: str, min_profit: int = 500, min_margin: float = 30.0):
    """調査の進捗と利益商品リストを返す"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")

    job = jobs[job_id]

    # 利益フィルタリング
    profitable = [
        item for item in job["results"]
        if item["profit"] >= min_profit and item["margin"] >= min_margin
    ]

    return {
        "done": job["done"],
        "total": len(job["products"]),
        "finished": job["finished"],
        "profitable_items": profitable,
    }


# ---- 調査ジョブ本体 ------------------------------------------

async def run_research(job_id: str):
    job = jobs[job_id]
    profitable_items = []

    for product in job["products"]:
        try:
            result = await analyze_product(product)
            if result:
                job["results"].append(result)
                if result["profit"] > 0:
                    profitable_items.append(result)
        except Exception as e:
            print(f"[ERROR] {product['title']}: {e}")
        finally:
            job["done"] += 1

        # 連続リクエストを避けるため待機（2〜4秒のランダムウェイト）
        await asyncio.sleep(2 + (hash(product["title"]) % 20) / 10)

    job["finished"] = True

    # 利益商品をスプレッドシートに書き出し
    if profitable_items:
        try:
            await asyncio.to_thread(append_profitable_items, profitable_items)
        except Exception as e:
            print(f"[SPREADSHEET ERROR] {e}")


async def analyze_product(product: dict) -> Optional[dict]:
    """1商品の利益計算を行う"""
    buy_price = product["price"]
    title = product["title"]

    # メルカリの売却済み相場（中央値）を取得
    median_price = await asyncio.to_thread(get_mercari_median_price, title)

    if median_price is None or median_price == 0:
        return None

    # 送料（タイトルからカテゴリを簡易判定）
    shipping = estimate_shipping(title)

    # 利益計算
    mercari_fee = int(median_price * MERCARI_FEE_RATE)
    fees = mercari_fee + shipping
    profit = median_price - buy_price - fees
    margin = round((profit / buy_price) * 100, 1) if buy_price > 0 else 0

    return {
        "title": title,
        "buy_price": buy_price,
        "median_price": median_price,
        "fees": fees,
        "profit": profit,
        "margin": margin,
        "url": product["url"],
        "imageUrl": product.get("imageUrl", ""),
    }


def estimate_shipping(title: str) -> int:
    """タイトルからカテゴリを簡易判定して送料を返す"""
    title_lower = title.lower()
    if any(k in title_lower for k in ["dvd", "blu-ray", "ブルーレイ", "映画"]):
        return SHIPPING_COST["dvd"]
    if any(k in title_lower for k in ["cd", "アルバム", "シングル"]):
        return SHIPPING_COST["cd"]
    if any(k in title_lower for k in ["ゲーム", "switch", "ps", "xbox", "ソフト"]):
        return SHIPPING_COST["game"]
    return SHIPPING_COST["default"]
