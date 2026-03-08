// ============================================================
// content_script.js
// ブックオフオンラインのページに注入されるスクリプト
// 商品情報を抽出してbackground.jsに送る
// ============================================================

(function () {
  "use strict";

  // ---- 商品情報の抽出 ----------------------------------------

  /**
   * 現在のページから商品リストを抽出する
   * ブックオフオンラインの商品一覧ページ・検索結果ページに対応
   * @returns {Array<{title: string, price: number, url: string, imageUrl: string}>}
   */
  function extractProducts() {
    const products = [];

    // ブックオフオンラインの商品カードセレクタ
    // ※ サイト改修時はここを修正する
    const itemSelectors = [
      ".c-product-item",         // 一般商品一覧
      ".p-search-result__item",  // 検索結果
      ".swiper-slide",           // おすすめ等スライダー（除外したい場合はコメントアウト）
    ];

    let itemElements = [];
    for (const sel of itemSelectors) {
      const found = document.querySelectorAll(sel);
      if (found.length > 0) {
        itemElements = Array.from(found);
        break;
      }
    }

    for (const el of itemElements) {
      try {
        // タイトル
        const titleEl =
          el.querySelector(".c-product-item__title") ||
          el.querySelector(".p-search-result__title") ||
          el.querySelector("h2") ||
          el.querySelector("h3");
        const title = titleEl ? titleEl.textContent.trim() : null;

        // 価格（税込）
        const priceEl =
          el.querySelector(".c-product-item__price") ||
          el.querySelector(".p-search-result__price") ||
          el.querySelector("[class*='price']");
        const priceText = priceEl ? priceEl.textContent.trim() : "";
        // 「1,234円」→ 1234
        const price = parseInt(priceText.replace(/[^0-9]/g, ""), 10);

        // 商品URL
        const linkEl = el.querySelector("a[href]");
        const url = linkEl
          ? new URL(linkEl.getAttribute("href"), location.origin).href
          : location.href;

        // サムネイル
        const imgEl = el.querySelector("img");
        const imageUrl = imgEl ? imgEl.src : "";

        if (title && !isNaN(price) && price > 0) {
          products.push({ title, price, url, imageUrl });
        }
      } catch (e) {
        // 1件のパース失敗はスキップ
        console.warn("[リサーチ] 商品パース失敗:", e);
      }
    }

    return products;
  }

  // ---- background.js からのメッセージ受信 ---------------------

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === "GET_PRODUCTS") {
      const products = extractProducts();
      console.log(`[リサーチ] ${products.length} 件の商品を検出`);
      sendResponse({ products });
    }
    // 非同期応答のために true を返す必要はないが念のため
    return true;
  });

  console.log("[リサーチ] content_script 読み込み完了");
})();
