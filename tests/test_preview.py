import importlib.util
import json
from pathlib import Path

from wanderlens.paths import repo_root
from wanderlens.preview import build_preview


def _private_keys(value):
    banned = {"gps", "lat", "lon", "latitude", "longitude"}
    if isinstance(value, dict):
        assert banned.isdisjoint(value)
        for item in value.values():
            _private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _private_keys(item)


def test_preview_snapshot_matches_catalog_and_hides_coordinates():
    payload = build_preview()
    text = json.dumps(payload, ensure_ascii=False)
    assert "22.291667" not in text
    _private_keys(payload)
    assert payload["preview"] is True
    assert payload["summary"]["with_gps"] == 1
    assert all(asset["has_gps"] is True or asset["has_gps"] is False for asset in payload["assets"])
    flux = next(model for model in payload["models"] if model["id"] == "flux.1-dev")
    assert flux["commercial_use"] == "disallowed"
    committed = json.loads((repo_root() / "web" / "preview" / "snapshot.json").read_text(encoding="utf-8"))
    assert [model["id"] for model in committed["models"]] == [model["id"] for model in payload["models"]]
    _private_keys(committed)


def test_pages_publish_requires_private_visibility():
    path = repo_root() / "scripts" / "ensure_private_pages.py"
    spec = importlib.util.spec_from_file_location("ensure_private_pages", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.site_is_private({"public": False, "html_url": "https://example.test"}) is True
    assert module.site_is_private({"public": True}) is False
    assert module.site_is_private({"message": "Not Found"}) is False
