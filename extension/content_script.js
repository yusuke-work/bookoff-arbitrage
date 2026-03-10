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

    // 商品カード要素を取得
    // 実際のHTMLでは ".productItem" クラスが使われている
    const itemElements = Array.from(document.querySelectorAll(".productItem"));

    for (const el of itemElements) {
      try {
        // タイトル
        const titleEl = el.querySelector(".productItem__title");
        const title = titleEl ? titleEl.textContent.trim() : null;

        // 価格（税込）
        // .productItem__price の中に "&yen;1,234" 形式のテキストが含まれる
        // 子要素（<small>など）のテキストを除外するため、firstChildのtextContentを使う
        const priceEl = el.querySelector(".productItem__price");
        let priceText = "";
        if (priceEl) {
          // firstChild はテキストノード（例: "¥110"）
          // childNodes[0] が価格の数値部分
          const firstTextNode = Array.from(priceEl.childNodes).find(
            (node) => node.nodeType === Node.TEXT_NODE
          );
          priceText = firstTextNode ? firstTextNode.textContent.trim() : priceEl.textContent.trim();
        }
        // 「¥1,234」→ 1234
        const price = parseInt(priceText.replace(/[^0-9]/g, ""), 10);

        // 商品URL
        // ".productItem__link" または ".productItem__image" のaタグを使う
        const linkEl =
          el.querySelector("a.productItem__link") ||
          el.querySelector("a.productItem__image") ||
          el.querySelector("a[href]");
        const url = linkEl
          ? new URL(linkEl.getAttribute("href"), location.origin).href
          : location.href;

        // サムネイル
        const imgEl =
          el.querySelector(".productItem__image img") ||
          el.querySelector("img");
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
    return true;
  });

  console.log("[リサーチ] content_script 読み込み完了");
})();