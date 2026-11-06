# Wanderlens 開發說明

使用者面向的說明使用繁體中文書面語。

這個倉庫把使用者自己的旅行照片與影片，在本機整理成待審閱草稿與數位影像包。原始檔、`data/`、模型權重、`.env` 與 `config/settings.yaml` 都不得提交。

## 保持這些邊界

- 描述提供者只有 `heuristic` 與 `openai`。新的開源模型寫進 `catalog/open_source_models.yaml`；不可直接商用的權重寫進 `catalog/extra/`，狀態維持 `restricted`。不要在程式裡散落模型名稱。
- `heuristic` 只能寫技術預檢，不得編成看起來像看過畫面的文案。
- 公開匯出必須移除 EXIF。索引可以保留座標，草稿與販售清單不可以。
- 不要由像素或座標推測城市，也不要建立人臉身分庫。人臉程式日後只可做遮罩。
- 不要加入瀏覽器自動登入、指紋瀏覽器、帳號養號或模擬互動。發佈只做到本機草稿；若要接平台，只用帳號持有人有權使用的官方 API，並保留人工確認。
- `mark-sale` 之後，販售包仍預設排除可辨識人物、未知人物與敏感內容。
- `recommended` 只能標在 `commercial_use: allowed`，且目前描述流程真的接得上的項目。授權欄位不是法律意見。
- 模型服務與整理流程分開。整理流程透過 HTTP 呼叫，不把某一個 CUDA 版本寫進預設依賴。
- `wanderlens ui` 只提供本機監控。回應不得包含座標，也不得提供素材原檔。`data/monitor.token` 是手機通行憑證，不得提交。
- 不要把監控頁發佈成公開網站。個人帳號的 GitHub Pages 即使倉庫是私人的也會對網際網路公開；只有能限制成倉庫成員時才可發佈。

## 常用指令

```bash
pip install -e ".[dev]"
pytest
wanderlens models list
wanderlens ingest
wanderlens describe --limit 10
wanderlens draft
wanderlens export-posts
```

改完清單後先執行 `pytest tests/test_catalog.py`。清單載入時會檢查識別碼、角色、授權與建議等級。
