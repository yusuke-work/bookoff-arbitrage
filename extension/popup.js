// ============================================================
// popup.js
// ポップアップのUI制御とバックエンドへのポーリング
// ============================================================

const BACKEND_URL = "http://localhost:8000";
let pollTimer = null;

// ---- DOM 参照 ------------------------------------------------
const startBtn      = document.getElementById("startBtn");
const progressDiv   = document.getElementById("progress");
const progressText  = document.getElementById("progressText");
const progressBar   = document.getElementById("progressBar");
const resultsDiv    = document.getElementById("results");
const errorMsg      = document.getElementById("errorMsg");
const emptyMsg      = document.getElementById("emptyMsg");
const minProfitInput = document.getElementById("minProfit");
const minMarginInput = document.getElementById("minMargin");

// ---- 初期化 --------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // 保存済みの設定と実行中のジョブを復元
  chrome.storage.local.get(
    ["minProfit", "minMargin", "currentJobId", "totalItems"],
    (data) => {
      const minProfit = data.minProfit != null ? data.minProfit : 500;
      const minMargin = data.minMargin != null ? data.minMargin : 30;

      minProfitInput.value = minProfit;
      minMarginInput.value = minMargin;

      // もし実行中のジョブ状態が残っていればポーリングを再開
      if (data.currentJobId && data.totalItems) {
        startBtn.disabled = true;
        showProgress(0, data.totalItems); // プログレスバーの初期化
        startPolling(data.currentJobId, data.totalItems, minProfit, minMargin);
      }
    }
  );

  startBtn.addEventListener("click", onStart);
});

// ---- 調査開始 ------------------------------------------------
async function onStart() {
  setError("");
  setEmpty(false);
  resultsDiv.innerHTML = "";
  startBtn.disabled = true;

  // 閾値を保存して、以前のジョブIDをクリア
  const minProfit = parseInt(minProfitInput.value, 10) || 500;
  const minMargin = parseInt(minMarginInput.value, 10) || 30;
  chrome.storage.local.set({ minProfit, minMargin });
  chrome.storage.local.remove(["currentJobId", "totalItems"]);

  try {
    // background.js 経由で調査開始
    const result = await sendMessage({ type: "START_RESEARCH", minProfit, minMargin });
    if (result.error) throw new Error(result.error);

    const { job_id, total } = result;
    showProgress(0, total);
    startPolling(job_id, total, minProfit, minMargin);

  } catch (err) {
    setError(err.message);
    startBtn.disabled = false;
  }
}

// ---- ポーリング ----------------------------------------------
function startPolling(jobId, total, minProfit, minMargin) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(
        `${BACKEND_URL}/status/${jobId}?min_profit=${minProfit}&min_margin=${minMargin}`
      );
      
      // バックエンドが再起動された場合などは 404 が返るためジョブを破棄してリセット
      if (res.status === 404) {
        throw new Error("ジョブが見つかりません。サーバーが再起動された可能性があります。");
      }
      if (!res.ok) throw new Error(`ステータス取得失敗: ${res.status}`);
      
      const data = await res.json();

      showProgress(data.done, total);
      renderResults(data.profitable_items);

      if (data.finished) {
        stopPollingAndCleanup();
        if (data.profitable_items.length === 0) setEmpty(true);
      }
    } catch (err) {
      stopPollingAndCleanup();
      setError("進捗取得エラー: " + err.message);
    }
  }, 2000); // 2秒ごとにポーリング
}

function stopPollingAndCleanup() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  startBtn.disabled = false;
  progressDiv.style.display = "none";
  // 調査完了後はジョブIDのキャッシュを削除（再リロード時に再開させないため）
  chrome.storage.local.remove(["currentJobId", "totalItems"]);
}

// ---- UI ヘルパー --------------------------------------------
function showProgress(done, total) {
  progressDiv.style.display = "block";
  progressText.textContent = `調査中... ${done} / ${total} 件`;
  progressBar.style.width = total > 0 ? `${Math.round((done / total) * 100)}%` : "0%";
}

function renderResults(items) {
  // 更新前に現在のスクロール位置を記憶する対応が必要であればやるが、
  // 今回は結果が追加される度に追記ではなく上書きなのでスクロールが上に飛んでしまう。
  resultsDiv.innerHTML = "";
  for (const item of items) {
    const div = document.createElement("div");
    div.className = "result-item";
    div.innerHTML = `
      <div class="result-title">
        ${escHtml(item.title)}
        <span class="profit-badge">+${item.profit.toLocaleString()}円 / ${item.margin}%</span>
      </div>
      <div class="result-detail">
        仕入れ: ${item.buy_price.toLocaleString()}円 ／
        相場中央値: ${item.median_price.toLocaleString()}円 ／
        手数料+送料: ${item.fees.toLocaleString()}円
      </div>
      <a class="result-link" href="${escHtml(item.url)}" target="_blank">商品ページを開く →</a>
    `;
    resultsDiv.appendChild(div);
  }
}

function setError(msg) {
  errorMsg.style.display = msg ? "block" : "none";
  errorMsg.textContent = msg;
}

function setEmpty(show) {
  emptyMsg.style.display = show ? "block" : "none";
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function sendMessage(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}
