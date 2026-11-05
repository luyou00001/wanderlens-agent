# 在 Linux 伺服器上執行

這個專案的整理流程只需要 CPU、Python 與磁碟。視覺模型另開一個服務，聽本機的 OpenAI 相容埠。兩邊不要裝在同一個會被 CUDA 升級打亂的環境裡。

## 1. 掛上既有照片

不要把多年的原始檔複製進 Git。把磁碟掛到素材庫，或直接把設定指到該磁碟：

```bash
sudo mkdir -p /mnt/travel
sudo mount /dev/disk/by-label/TRAVEL /mnt/travel
```

`config/settings.yaml`：

```yaml
vault_dir: /mnt/travel
library_path: /var/lib/wanderlens/library.json
exports_dir: /var/lib/wanderlens/exports
cache_dir: /var/lib/wanderlens/cache
provider: heuristic
```

請用掛載，不要用指向外部磁碟的符號連結。程式不會跟隨目錄捷徑，以免掃描意外走出素材庫。

HEIC 需要系統的 libheif，以及 Python 的解碼器。尚未安裝時，那些檔案仍會被登記，並標成無法解碼。

影片抽幀需要 `ffmpeg` 與 `ffprobe`：

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## 2. 安裝整理流程

```bash
cd /opt/wanderlens-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
wanderlens ingest
wanderlens describe --limit 10
```

`scripts/bootstrap-linux.sh` 會建立虛擬環境。`scripts/run-mvp.sh` 會依序執行清點、描述、草稿與匯出。

## 3. 啟動視覺模型

以下命令是工作負載上的起點，不是唯一的正式參數。單張照片不需要 256K 上下文；上下文過長很容易把顯存吃完。請以該模型卡當時的說明為準。

SGLang，以 Qwen3.5-9B 為例：

```bash
python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-9B \
  --host 127.0.0.1 \
  --port 8000 \
  --tp-size 1 \
  --mem-fraction-static 0.8 \
  --context-length 8192 \
  --reasoning-parser qwen3
```

或 vLLM：

```bash
vllm serve Qwen/Qwen3.5-9B \
  --host 127.0.0.1 \
  --port 8000 \
  --max-model-len 8192
```

然後在整理流程的環境：

```bash
export WANDERLENS_PROVIDER=openai
export WANDERLENS_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
export WANDERLENS_OPENAI_MODEL=Qwen/Qwen3.5-9B
export WANDERLENS_OPENAI_API_KEY=EMPTY
wanderlens describe --force --limit 10
```

`WANDERLENS_OPENAI_MODEL` 要填服務實際註冊的名稱。Ollama 的名稱常常不等於 Hugging Face 識別碼，位址通常是 `http://127.0.0.1:11434/v1`。

Qwen3.5 預設會先產生思考過程。客戶端會送出 `enable_thinking: false` 與 `/no_think`。若某個服務把這個欄位當成錯誤並回覆 HTTP 400，請在設定檔把 `send_disable_thinking` 設為 `false`。

傳給模型的影像會先縮到長邊 1280。原始檔不會被改寫。

## 4. 容器

`Dockerfile` 安裝的是整理流程與 ffmpeg，不下載權重。

```bash
docker compose build
docker compose run --rm pipeline ingest
docker compose run --rm pipeline describe --limit 10
```

顯示卡留給模型服務即可，不必把整個整理容器改成 GPU 映像。

## 5. 定時清點

可以之後再用 systemd timer 執行 `wanderlens ingest` 與 `wanderlens describe`。請讓它只寫本機索引與草稿，不要在 timer 裡發佈或上傳。
