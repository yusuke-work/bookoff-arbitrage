# ============================================================
# main.py
# FastAPI バックエンド
# Chrome拡張機能から商品リストを受け取り、メルカリ相場調査を行う
# ============================================================

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
import asyncio
import time

from mercari_scraper import get_mercari_median_price, _scraper_instance
from spreadsheet import append_profitable_items

app = FastAPI(title="ブックオフせどりリサーチAPI")

# Chrome拡張機能からのリクエストを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- サーバーライフサイクル ----------------------------------
@app.on_event("shutdown")
async def shutdown_event():
    """サーバー終了時に Playwright のブラウザ等のリソースをクリーンアップ"""
    await _scraper_instance.close()

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
# { job_id: { "products": [...], "results": [...], "done": int, "finished": bool, "created_at": float } }
jobs: dict[str, dict] = {}

def cleanup_old_jobs(max_age_seconds: int = 3600):
    """一定時間経過した古いジョブを削除してメモリリークを防ぐ"""
    now = time.time()
    stale_jobs = [j_id for j_id, j_data in jobs.items() if now - j_data["created_at"] > max_age_seconds]
    for j_id in stale_jobs:
        del jobs[j_id]

# ---- スキーマ ------------------------------------------------

class Product(BaseModel):
    title: str
    price: int       # ブックオフでの仕入れ価格（円）
    url: str
    imageUrl: Optional[str] = ""

class ResearchRequest(BaseModel):
    products: List[Product]
    min_profit: int = 500
    min_margin: float = 30.0

# ---- エンドポイント ------------------------------------------

@app.post("/research")
async def start_research(req: ResearchRequest, background_tasks: BackgroundTasks):
    """調査ジョブを開始して job_id を返す"""
    # 定期的に古いジョブをお掃除
    cleanup_old_jobs()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "products": [p.model_dump() for p in req.products],
        "results": [],
        "done": 0,
        "finished": False,
        "created_at": time.time(),
        "min_profit": req.min_profit,
        "min_margin": req.min_margin,
    }
    # バックグラウンドで調査を実行
    background_tasks.add_task(run_research, job_id)
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

    min_profit = job.get("min_profit", 500)
    min_margin = job.get("min_margin", 30.0)

    for product in job["products"]:
        try:
            result = await analyze_product(product)
            if result:
                job["results"].append(result)
                if result["profit"] >= min_profit and result["margin"] >= min_margin:
                    profitable_items.append(result)
        except Exception as e:
            print(f"[ERROR] {product['title']}: {e}")
        finally:
            job["done"] += 1

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

    # メルカリの売却済み相場（中央値）を取得（Playwrightの並行処理管理を含む）
    median_price = await get_mercari_median_price(title)

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
