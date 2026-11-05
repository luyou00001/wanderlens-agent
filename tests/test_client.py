import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from wanderlens.config import Settings
from wanderlens.openai_client import OpenAICompatibleClient
from wanderlens.pipeline import describe, ingest


def test_openai_compatible_client_reads_json_caption(tmp_path: Path):
    image_path = tmp_path / "red.jpg"
    Image.new("RGB", (32, 24), (200, 20, 20)).save(image_path, format="JPEG")
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            seen["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
            content = json.dumps(
                {
                    "caption_zh_hant": "紅色測試畫面。",
                    "caption_en": "A red test frame.",
                    "subjects": ["色塊"],
                    "setting": "純色背景",
                    "mood": "平靜",
                    "contains_identifiable_people": False,
                    "aesthetic_score": 0.2,
                    "suggested_products": ["carousel"],
                    "sensitive_content": False,
                    "quality_notes": "測試",
                }
            )
            raw = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        client = OpenAICompatibleClient(
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="EMPTY",
            model="test-model",
            timeout=5,
            max_edge=64,
            send_disable_thinking=True,
            prompt="請描述。",
        )
        semantic = client.describe_image(image_path)
    finally:
        server.shutdown()
        server.server_close()

    assert semantic["caption_zh_hant"] == "紅色測試畫面。"
    assert seen["body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert seen["body"]["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_describe_reports_connection_failure(tmp_path: Path):
    vault = tmp_path / "vault"
    inbox = vault / "inbox"
    inbox.mkdir(parents=True)
    Image.new("RGB", (16, 16), (1, 2, 3)).save(inbox / "one.jpg", format="JPEG")
    settings = Settings(
        vault_dir=vault,
        library_path=tmp_path / "library.json",
        exports_dir=tmp_path / "exports",
        cache_dir=tmp_path / "cache",
        provider="openai",
        openai_base_url="http://127.0.0.1:9/v1",
        openai_model="Qwen/Qwen3.5-9B",
        request_timeout_s=2,
    )
    ingest(settings, inbox)
    report = describe(settings)
    assert report.described == 0
    assert report.failed == 1
    assert "無法連線" in report.failures[0][1]
