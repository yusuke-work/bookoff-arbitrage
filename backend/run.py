# run.py
# uvicorn の起動スクリプト
# ※ 現在は sync_playwright + asyncio.to_thread を使用しているため、
#    EventLoop のポリシー変更は不要です。
#    このファイルは --reload を使いたい場合の代替として残しています。

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)