# 監控頁視覺說明

這個頁面給本機使用。執行 `wanderlens ui` 後，用瀏覽器打開終端機印出的網址。樣式與程式使用相對路徑，所以同一個 `web/` 目錄也可以放到子路徑網站。不要用檔案總管直接點開 `index.html`，否則模組與資料介面都不會載入。

沒有本機索引時，頁面會改讀 `preview/snapshot.json`。那是預覽素材，不是使用者的照片。不要把座標加進這個檔。

頁面讀取索引摘要。它不提供原始照片，也不顯示座標。美化時請維持這兩件事。

## 可以改的地方

視覺變數集中在 [css/tokens.css](css/tokens.css)。顏色、字體、間距、圓角與側欄寬度都放在那裡。其他樣式表只使用 `var(--token)`。

| 檔案 | 職責 |
| --- | --- |
| `index.html` | 側欄、頂部列與掛載點。分頁按鈕要保留 `data-view`。 |
| `css/tokens.css` | 之後調整視覺時優先改這裡。 |
| `css/base.css` | 重置、字級與焦點。 |
| `css/layout.css` | 側欄、頂部列、主區與窄螢幕。 |
| `css/components.css` | 卡片、表格、標籤、按鈕與表單。 |
| `js/` | 資料與畫面結構。改版面時盡量不要把路徑寫進 `innerHTML`。 |

主內容會放進 `<main class="stage" data-stage>`。請保留 `data-stage`。素材表與模型表的結果區使用 `data-results`，自動更新時只替換這塊，避免把正在輸入的搜尋框清掉。

網址列的 `#overview`、`#library`、`#models`、`#activity` 會打開對應分頁。

## 資料從哪裡來

同網域的 JSON：

- `GET /api/status`
- `GET /api/summary`
- `GET /api/assets`
- `GET /api/assets/<id>`
- `GET /api/models`
- `GET /api/trips`

約每 3 秒重讀一次。`has_gps` 只表示索引裡有沒有定位，回應裡不會有經緯度。不要另外向頁面請求素材庫裡的原始檔。

## 不要做的事

- 不要在 `tokens.css` 以外寫色碼。
- 不要用 `innerHTML` 放入檔名、描述或模型說明。
- 不要把座標、地圖或原圖預覽加回來。
- 不要假設這個頁面有登入。它預設只聽本機。
