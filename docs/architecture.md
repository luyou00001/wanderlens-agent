# 架構

整理流程以本機索引為中心。照片與影片留在素材庫，Git 只保存程式、提示詞與模型清單。

```text
assets_vault/inbox
        │  wanderlens ingest
        ▼
data/library/library.json
        │  wanderlens describe
        │     heuristic：技術預檢，不宣稱看過畫面
        │     openai：本機 OpenAI 相容視覺服務
        ▼
   analysis.semantic
        │  wanderlens draft
        ▼
 Instagram／小紅書／X 草稿
        │
        ├─ wanderlens export-posts     待審閱目錄，公開 JPEG 不含 EXIF
        └─ wanderlens mark-sale
                 │
                 ▼
           wanderlens bundle           尚未上架的數位影像草稿包
```

## 模組

| 路徑 | 職責 |
| --- | --- |
| `pipeline.py` | 清點、描述、草稿，以及販售與發佈標記 |
| `media.py` | 雜湊、EXIF、技術分數、公開 JPEG、影片抽幀 |
| `trips.py` | 依拍攝時間分行程；距離門檻預設關閉 |
| `openai_client.py` | 把單張圖送到 `/v1/chat/completions` |
| `drafts.py` | 產生三種平台、繁體中文與英文的草稿 |
| `publishing.py` | 寫出待審閱 Markdown 與 JSON |
| `commerce.py` | 決定哪些靜態影像可以進入草稿包 |
| `catalog.py` | 讀取並檢查開源模型清單 |

描述模型只透過兩種提供者接上：`heuristic` 與 `openai`。Florence-2、美學分數、放大、去背、語音與鏡頭切分都先列在清單，等對應的適配器有明確用途時再寫。這樣換模型時，通常只改服務端的模型名稱。

## 索引裡有什麼

`library.json` 可以包含拍攝座標、相機型號與檔案路徑，因此整個 `data/` 都已忽略。公開匯出只保留尺寸、你填寫的地點標記、相機型號與描述來源，不寫座標。

相同內容的檔案會合成一筆。識別碼取自檔案大小與頭尾各 1MB 的 SHA-256 前 16 碼，用來避免把整部影片讀進記憶體。它不是密碼學簽章。

沒有拍攝時間的檔案會進入 `trip-undated`，不會用檔案修改時間冒充拍攝時間。你之後用 `label-place` 補上的地名，會寫成「地點標記」，與模型描述分開。

## 發佈與販售的閘門

`export-posts` 永遠寫本機檔。沒有畫面描述時，正文會保留「待視覺描述」。`mark-publish` 只接受已經有畫面描述的草稿，而且不會把內容送到任何平台。

`bundle` 預設排除：

- 影片與無法解碼的檔案
- 長邊低於門檻的影像
- 尚未 `mark-sale` 的影像
- 敏感內容
- 含可辨識人物，或尚未判斷人物的影像

`--allow-people` 只代表你另外確認過權利之後，願意把含人物的影像放進這次草稿包。它不會辨識那些人是誰。

## 明確不做的事

- 不使用瀏覽器自動登入、指紋瀏覽器或模擬互動來經營帳號。
- 不把座標反查成城市，也不從畫面推測私人位置。
- 不建立人臉特徵庫。日後若做人臉處理，只限於遮罩。
- 不把非商業授權的配樂模型放進預設商品。
