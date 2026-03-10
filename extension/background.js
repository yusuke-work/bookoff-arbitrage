// ============================================================
// background.js
// Service Worker: popup.js からの指示を受け、
// content_script → Python バックエンドへの橋渡しをする
// ============================================================

const BACKEND_URL = "http://localhost:8000"; // Pythonサーバーのアドレス

// ---- popup.js からのメッセージ受信 --------------------------

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "START_RESEARCH") {
    handleResearch(message.minProfit, message.minMargin)
      .then(sendResponse)
      .catch((err) => {
        sendResponse({ error: err.message });
      });
    return true; // 非同期応答を許可
  }

  if (message.type === "GET_STATUS") {
    sendResponse({ status: "ready" });
  }
});

// ---- メイン処理 ----------------------------------------------

async function handleResearch(minProfit = 500, minMargin = 30) {
  // 1. アクティブタブの判定
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || !tab.url.includes("shopping.bookoff.co.jp")) {
    throw new Error("ブックオフオンラインのページを開いてから実行してください");
  }

  // content_script から商品リストを取得
  let response;
  try {
    response = await chrome.tabs.sendMessage(tab.id, { type: "GET_PRODUCTS" });
  } catch (err) {
    // 拡張機能をインストールした直後や、タブが完全に読み込まれていない場合のエラー
    throw new Error("ページの読み込みが完了していません。ページを再読み込みしてから再度お試しください。");
  }

  const products = response?.products ?? [];

  if (products.length === 0) {
    throw new Error("商品が見つかりませんでした。ページを確認してください。");
  }

  // 2. Pythonバックエンドに商品リストを送信して調査を開始
  let res;
  try {
    res = await fetch(`${BACKEND_URL}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        products: products,
        min_profit: minProfit,
        min_margin: minMargin,
      }),
    });
  } catch (err) {
    throw new Error("バックエンドサーバーに接続できません。サーバーが起動しているか確認してください。");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`バックエンドエラー: ${res.status} ${text}`);
  }

  const data = await res.json();
  // { job_id: "xxxx", total: 10 }

  // 3. ジョブIDをストレージに保存（popup.jsから状態を復帰するため）
  await chrome.storage.local.set({ currentJobId: data.job_id, totalItems: data.total });

  return { job_id: data.job_id, total: data.total };
}
