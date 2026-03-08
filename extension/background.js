// ============================================================
// background.js
// Service Worker: popup.js からの指示を受け、
// content_script → Python バックエンドへの橋渡しをする
// ============================================================

const BACKEND_URL = "http://localhost:8000"; // Pythonサーバーのアドレス

// ---- popup.js からのメッセージ受信 --------------------------

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "START_RESEARCH") {
    handleResearch().then(sendResponse).catch((err) => {
      sendResponse({ error: err.message });
    });
    return true; // 非同期応答を許可
  }

  if (message.type === "GET_STATUS") {
    sendResponse({ status: "ready" });
  }
});

// ---- メイン処理 ----------------------------------------------

async function handleResearch() {
  // 1. アクティブタブの content_script から商品リストを取得
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || !tab.url.includes("shopping.bookoff.co.jp")) {
    throw new Error("ブックオフオンラインのページを開いてから実行してください");
  }

  const response = await chrome.tabs.sendMessage(tab.id, { type: "GET_PRODUCTS" });
  const products = response?.products ?? [];

  if (products.length === 0) {
    throw new Error("商品が見つかりませんでした。ページを確認してください。");
  }

  // 2. Pythonバックエンドに商品リストを送信して調査を開始
  const res = await fetch(`${BACKEND_URL}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ products }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`バックエンドエラー: ${res.status} ${text}`);
  }

  const data = await res.json();
  // { job_id: "xxxx", total: 10 }

  // 3. ジョブIDをストレージに保存（popup.jsからポーリングで参照）
  await chrome.storage.local.set({ currentJobId: data.job_id, totalItems: data.total });

  return { job_id: data.job_id, total: data.total };
}
