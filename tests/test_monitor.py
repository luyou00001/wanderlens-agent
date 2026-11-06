import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from wanderlens.config import Settings
from wanderlens.monitor import create_server


def _settings(tmp_path, library: dict | None):
    library_path = tmp_path / "library.json"
    if library is not None:
        library_path.write_text(json.dumps(library), encoding="utf-8")
    return Settings(
        vault_dir=tmp_path / "vault",
        library_path=library_path,
        exports_dir=tmp_path / "exports",
        cache_dir=tmp_path / "cache",
    )


def _start(settings):
    server = create_server(settings, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _read(port, path):
    with urlopen(f"http://127.0.0.1:{port}{path}") as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def _private_keys(value):
    banned = {"gps", "lat", "lon", "latitude", "longitude"}
    if isinstance(value, dict):
        assert banned.isdisjoint(value)
        for item in value.values():
            _private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _private_keys(item)


def test_monitor_hides_coordinates_and_serves_the_page(tmp_path):
    library = {
        "schema_version": 1,
        "assets": {
            "abc123": {
                "id": "abc123",
                "relative_path": "inbox/harbor.jpg",
                "media_type": "image",
                "byte_size": 1200,
                "captured_at": "2024-03-01T08:00:00+00:00",
                "gps": {"lat": 22.291667, "lon": 114.154167},
                "camera_model": "ILCE-7M4",
                "analysis": {
                    "provider": "openai",
                    "model": "Qwen/Qwen3.5-9B",
                    "summary_zh_hant": "技術預檢不該出現在這裡。",
                    "semantic": {
                        "lat": 22.291667,
                        "contains_identifiable_people": False,
                        "caption_zh_hant": "岸邊",
                    },
                },
                "drafts": [
                    {
                        "platform": "x",
                        "language": "zh-Hant",
                        "title": "岸邊",
                        "needs_vision_model": False,
                        "copy_text": "岸邊",
                        "gps": {"lat": 22.291667},
                    }
                ],
            }
        },
    }
    server = _start(_settings(tmp_path, library))
    port = server.server_address[1]
    try:
        status, content_type, page = _read(port, "/")
        assert status == 200
        assert "text/html" in content_type
        head = Request(f"http://127.0.0.1:{port}/", method="HEAD")
        with urlopen(head) as response:
            assert response.status == 200
            assert response.read() == b""
        html = page.decode("utf-8")
        assert 'type="module"' in html
        assert 'src="js/main.js"' in html
        assert 'href="css/tokens.css"' in html
        assert "apple-mobile-web-app-capable" in html
        assert "manifest.webmanifest" in html
        assert "data-stage" in html
        _status, manifest_type, manifest = _read(port, "/manifest.webmanifest")
        assert "json" in manifest_type
        assert b"Wanderlens" in manifest
        _status, icon_type, icon = _read(port, "/icons/apple-touch-icon.png")
        assert "image/png" in icon_type
        assert icon.startswith(b"\x89PNG")
        assert "22.291667" not in html

        _status, css_type, css = _read(port, "/css/tokens.css")
        assert "text/css" in css_type
        assert "--color-bg" in css.decode("utf-8")

        for payload_path in ("/api/summary", "/api/assets", "/api/assets/abc123", "/api/trips"):
            _status, _kind, body = _read(port, payload_path)
            text = body.decode("utf-8")
            assert "22.291667" not in text
            assert "114.154167" not in text
            _private_keys(json.loads(text))

        detail = json.loads(_read(port, "/api/assets/abc123")[2])
        assert detail["has_gps"] is True
        assert detail["camera_model"] == "ILCE-7M4"
        assert detail["people"] is False
        summary = json.loads(_read(port, "/api/summary")[2])
        assert summary["assets"] == 1
        assert summary["with_gps"] == 1
        assert summary["described"] == 1

        models = json.loads(_read(port, "/api/models?query=flux.1-dev")[2])
        flux = next(model for model in models["models"] if model["id"] == "flux.1-dev")
        assert flux["commercial_use"] == "disallowed"
        assert flux["status"] == "restricted"

        try:
            urlopen(f"http://127.0.0.1:{port}/css/../../pyproject.toml")
            raise AssertionError("路徑穿越應該被拒絕")
        except HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_phone_access_requires_the_printed_key():
    from wanderlens.monitor import access_granted, load_or_create_token

    key = "secret-token-value"
    assert access_granted("127.0.0.1", "", "", "", key) is True
    assert access_granted("192.168.1.20", "", "", "", key) is False
    assert access_granted("192.168.1.20", "", key, "", key) is True
    assert access_granted("192.168.1.20", key, "", "", key) is True
    assert access_granted("192.168.1.20", "", "", key, key) is True
    assert access_granted("10.0.0.8", "", "wrong-token-value", "", key) is False
    assert access_granted("192.168.1.20", "", "", "", None) is True


def test_phone_token_is_reused(tmp_path):
    from wanderlens.monitor import load_or_create_token

    path = tmp_path / "monitor.token"
    first = load_or_create_token(path)
    assert load_or_create_token(path) == first
    assert path.read_text(encoding="utf-8").strip() == first


def test_monitor_opens_before_ingest(tmp_path):
    server = _start(_settings(tmp_path, None))
    port = server.server_address[1]
    try:
        summary = json.loads(_read(port, "/api/summary")[2])
        assert summary["library_ready"] is False
        assert summary["assets"] == 0
        assert "ingest" in summary["library_error"]
        status, _kind, page = _read(port, "/")
        assert status == 200
        assert b"data-stage" in page
    finally:
        server.shutdown()
        server.server_close()
