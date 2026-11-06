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


def _preview_guard():
    path = repo_root() / "scripts" / "ensure_public_preview.py"
    spec = importlib.util.spec_from_file_location("ensure_public_preview", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_preview_accepts_the_checked_in_site():
    module = _preview_guard()
    module.assert_public_preview(repo_root() / "web")


def test_public_preview_rejects_coordinates_tokens_and_media(tmp_path: Path):
    module = _preview_guard()
    root = tmp_path / "web"
    (root / "preview").mkdir(parents=True)
    (root / "index.html").write_text("<!DOCTYPE html><title>預覽</title>", encoding="utf-8")
    (root / "preview" / "snapshot.json").write_text(
        '{"preview": true, "assets": [{"id": "preview-photo", "relative_path": "preview/shore.jpg", "latitude": 25.0}]}',
        encoding="utf-8",
    )
    try:
        module.assert_public_preview(root)
    except module.PreviewPublishError as exc:
        assert "座標" in str(exc)
    else:
        raise AssertionError("含座標的預覽頁不應通過。")

    (root / "preview" / "snapshot.json").write_text(
        '{"preview": true, "assets": [{"id": "preview-photo", "relative_path": "preview/shore.jpg"}]}',
        encoding="utf-8",
    )
    (root / "photo.jpg").write_bytes(b"not-a-real-photo")
    (root / "monitor.token").write_text("secret-token-value", encoding="utf-8")
    try:
        module.assert_public_preview(root)
    except module.PreviewPublishError as exc:
        message = str(exc)
        assert "photo.jpg" in message
        assert "monitor.token" in message
    else:
        raise AssertionError("原檔與通行憑證不應通過。")
