# Wanderlens Agent

Wanderlens Agent 在你自己的 Linux 伺服器上，把多年累積的旅行照片與影片整理成可審閱的社群草稿，以及可再經人工確認後販售的數位影像包。原始檔與模型權重留在本機，不會進入 Git。

目前已接通的流程是：

1. 清點素材，讀取尺寸、拍攝時間與 EXIF。
2. 依照拍攝時間把素材分成行程。地點名稱只接受你事後標註，程式不會由座標或畫面猜測城市。
3. 先做技術預檢，或呼叫你本機的 OpenAI 相容視覺模型。
4. 產生 Instagram、小紅書與 X 的草稿。
5. 匯出待審閱目錄。公開 JPEG 會移除 EXIF，包含定位資訊。
6. 在你明確標記可販售，且畫面被標成不含可辨識人物之後，組成數位影像草稿包。

程式不會登入社群網站，也不會自動上架。發佈與販售都留在你確認之後。

## 目錄

```text
assets_vault/inbox/          放入或掛載原始照片與影片
catalog/open_source_models.yaml
catalog/extra/                 不可直接用於販售的開放權重
config/prompts/vision_json.txt
web/                           本機監控頁
config/settings.example.yaml
src/wanderlens/              清點、描述、草稿、匯出
data/library/                本機索引，含私人 EXIF，不提交
data/exports/                待審閱草稿與影像包，不提交
```

## 開始

需求為 Python 3.11 或以上。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
wanderlens models list
```

把照片或影片放進 `assets_vault/inbox/` 之後：

```bash
wanderlens ingest
wanderlens describe --limit 10
wanderlens draft
wanderlens export-posts
wanderlens list
```

第一次的 `describe` 使用技術預檢，文案會明確寫成「這不是畫面描述」，避免尚未看過畫面就被拿去發佈。成果在 `data/exports/posts/`，請先看 `REVIEW.md`。

有畫面描述之後，可以標記一筆草稿供你自行貼上：

```bash
wanderlens mark-publish --asset-id <索引裡的 id> --yes
wanderlens label-place --asset-id <id> --place "你自己知道的地名"
```

販售草稿包預設要求長邊至少 1600 像素、已標記可販售、且模型明確判斷不含可辨識人物：

```bash
wanderlens mark-sale --asset-id <id> --yes
wanderlens bundle
```

`bundle` 只寫出本機目錄，不會上傳到任何商店。

## 監控頁

索引建立之後，可以開一個只在本機閱讀的頁面：

```bash
wanderlens ui
```

瀏覽器打開終端機印出的網址，預設是 <http://127.0.0.1:8765/>。頁面大約每 3 秒重讀一次索引，用來查看清點、描述、草稿與模型清單。它不提供原始照片，也不顯示座標。

樣式集中在 `web/css/tokens.css`。之後若要調整版面，先看 [web/DESIGN.md](web/DESIGN.md)。只在這台電腦上看時，維持預設的 `127.0.0.1`。

### 在 iPhone 上打開

電腦與 iPhone 連同一個 Wi-Fi 後：

```bash
wanderlens ui --lan
```

終端機會印出電腦網址，以及給 iPhone 的網址。用 Safari 打開 iPhone 那一行，點分享，再選加入主畫面。之後主畫面圖示會以網頁方式打開，不會經過 App Store。

iPhone 網址裡的 `k` 是通行憑證。不要轉傳，也不要提交 `data/monitor.token`。電腦本機的 `http://127.0.0.1:8765/` 不需要這組憑證。

現階段不把這個頁面改寫成 Expo。Expo Go 是給 React Native 開發時預覽的，套用在這裡就要重寫介面。若以後要做成可安裝的 iOS App，再考慮 Capacitor，它可以包住現在這個網頁。

### 給其他開發成員看的網址

推上 `main` 之後，GitHub Actions 會嘗試把 `web/` 發佈成只有倉庫成員能開的網站。這個帳號是個人帳號。GitHub 的規則是：個人帳號即使倉庫是私人的，Pages 網站仍會對整個網際網路公開；只有企業版雲端的組織倉庫能改成「有讀取權限的人才能看」。

因此目前不會把監控頁發佈出去。你之後把開發成員加進這個私人倉庫，他們可以 clone 之後在自己的電腦看版面：

```bash
python3 -m http.server -d web 8765
```

這個靜態網址只會顯示預覽素材與模型清單，不是你的照片，也沒有座標。真正的索引仍要在放照片的那台機器執行 `wanderlens ui`。若日後把倉庫轉到支援私人 Pages 的組織，同一個工作流程才會發佈。

## 接上本機模型

模型服務與這個專案分成兩個環境，中間只用 HTTP。CUDA 與權重的變動就不會綁住整理流程。

```bash
cp .env.example .env
# 編輯 .env：WANDERLENS_PROVIDER=openai，並填入服務實際註冊的模型名稱
wanderlens describe --force --limit 10
```

伺服器安裝、顯存與啟動方式見 [docs/linux-server.md](docs/linux-server.md)。模型怎麼選見 [docs/models.md](docs/models.md)。可商用的項目在 [catalog/open_source_models.yaml](catalog/open_source_models.yaml)，不可直接用於販售的項目在 [catalog/extra/](catalog/extra/)。用 `wanderlens models list` 與 `wanderlens models show <id>` 查閱。

## 權利與人物

只整理你有權使用的照片與影片。含可辨識人物的影像預設不能進入販售包。程式不建立人臉身分庫，也不從像素反推拍攝地點。

模型授權各不相同。清單裡的 `commercial_use` 是閱讀筆記，不是法律意見；正式販售前請再核對模型卡。`recommended` 只會標在允許商用、而且目前描述流程接得上的項目。

若日後用超解析度放大入選照片，商品頁必須如實說明，不要寫成相機原生解析度。

## 測試

```bash
pytest
```

測試使用臨時小圖，不需要顯示卡，也不會讀取 `assets_vault` 裡的真實素材。

## 文件

- [架構](docs/architecture.md)
- [模型清單的用法](docs/models.md)
- [Linux 伺服器](docs/linux-server.md)
- [後續順序](docs/roadmap.md)
