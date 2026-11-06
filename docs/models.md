# 開源模型清單

機器可讀的清單是 [catalog/open_source_models.yaml](../catalog/open_source_models.yaml)。不可自由商用或附帶條件、不該直接拿去販售的權重另收在 [catalog/extra/noncommercial.yaml](../catalog/extra/noncommercial.yaml)，載入時會併入。新增模型時維持下列約束：

- `id` 使用小寫、數字與連字號。
- `commercial_use` 只能是 `allowed`、`disallowed`、`conditional` 或 `unknown`。
- `status: recommended` 或 `alternate` 的項目必須是 `allowed`。
- `recommended` 還必須能透過現有的 OpenAI 相容描述流程使用。目前只有 `qwen3.5-9b`。
- 非商業或附帶條件的權重使用 `restricted`，不要放進預設流程。
- 這份分類是閱讀模型卡後的筆記，正式商用前仍要重讀授權。

查看方式：

```bash
wanderlens models list
wanderlens models list --role vision_language --commercial allowed
wanderlens models list --query whisper --json
wanderlens models show qwen3.5-9b
```

## 角色

| 角色 | 用途 |
| --- | --- |
| `vision_language` | 描述照片、標註主體、寫草稿 |
| `video_understanding` | 理解影片或連續畫面 |
| `shot_detection` | 把長片切成鏡頭 |
| `speech_transcription` | 轉錄真正的人聲 |
| `image_embedding` | 以圖找圖，或以文字找圖 |
| `text_embedding` | 搜尋文案；商業索引請用可商用模型 |
| `aesthetic_quality` | 技術品質或美學分數 |
| `image_restoration` | 放大或修復已入選的照片 |
| `image_generation` | 由文字產生影像；預設不進入商品 |
| `image_editing` | 依條件重繪或補畫既有照片 |
| `video_generation` | 由影像產生影片；預設不進入商品 |
| `matting` | 去背 |
| `text_generation` | 純文字潤飾，不能拿來描述照片 |
| `audio_generation` | 生成聲音；預設不進入商品 |
| `ocr` | 讀取路標、菜單、車票 |
| `pose` | 估計姿態與構圖，不用來辨識身分 |
| `privacy_redaction` | 只用於遮罩，不用於辨識身分 |

## 建議的使用順序

先用技術預檢把流程跑通。伺服器準備好之後，依顯存選擇一個視覺模型，透過 vLLM、SGLang 或 Ollama 提供 OpenAI 相容端點。

| 約略顯存 | 優先考慮 | 用途 |
| --- | --- | --- |
| 6–8GB | `qwen3.5-4b`、`qwen3-vl-4b-instruct`、`gemma-4-e2b-it`、`minicpm-v-4.6` | 先跑通，或做大量粗篩 |
| 12–16GB | `qwen3.5-9b`、`qwen3-vl-8b-instruct`、`internvl3.5-8b` | 單機正式描述 |
| 24GB 以上 | `internvl3.5-30b-a3b` | 對入選作品做第二輪，不必用來掃完整個圖庫 |

數字是權重量級，不是保證。量化格式、上下文長度和照片解析度都會改變實際占用。

照片很多時，不要一開始就把每張圖送進最大的模型。較合理的順序是：

1. 技術預檢與 EXIF 先去掉明顯損壞或重複的檔案。
2. 長片先用 `pyscenedetect` 或 `transnetv2` 切鏡頭，再用 `ffmpeg` 抽少數幀。本版的 OpenAI 提供者已會抽幀。
3. 入選的靜態影像才考慮 `realesrgan-x4plus`。
4. 圖庫索引優先比較 `siglip2-so400m`（可用文字搜尋）與 `dinov2-large`（只看構圖與外觀）。
5. 有人說話的影片再用 `whisper-large-v3-turbo`。風聲不必強行轉錄。

`jina-clip-v2` 與 `musicgen-medium` 的權重不可用於商業用途。`jina-clip-v1` 是 Apache-2.0，不要把兩代看成同一份授權。`stable-audio-open-1.0` 有額外商業條件，預設不使用。`q-align` 與 `pyiqa` 裡各個分數模型的授權並不統一，在確認之前只可作內部實驗。

## 不可自由商用

`catalog/extra/noncommercial.yaml` 收的是不能直接用於販售，或還要另外確認條款的權重。狀態都是 `restricted`，不會變成預設描述模型。

```bash
wanderlens models list --commercial disallowed
wanderlens models list --commercial conditional
```

這些權重可以留在伺服器上做授權允許的實驗。不要用它們產生要上架的圖片、影片、配樂或文案，也不要放進對外服務。附條件的項目，例如 Stability 社群授權、Llama 社群授權與 Gemma 條款，在你確認條件之前同樣不要進入商品。

SDXL 本體與 Stable Diffusion 1.x 多為 OpenRAIL，有使用限制，但不是這份非商用清單的對象。`sdxl-turbo` 的公開授權檔與商業使用方式不同，因此單獨收錄，使用前要再讀模型卡。

FLUX.1 dev 系列的權重本身不可用於商業生產。不要用它們產出上架商品。清單裡的授權筆記不是法律意見。

Florence-2、InternVideo3、Whisper、Real-ESRGAN 與 BiRefNet 已列入清單，但這個版本還沒有各自的適配器。視覺描述目前不需要把它們寫死在程式裡。
