import json
from pathlib import Path

import pytest
from PIL import Image
from PIL.ExifTags import IFD
from PIL.TiffImagePlugin import IFDRational

from wanderlens.cli import main
from wanderlens.commerce import exclusion_reason, export_bundle
from wanderlens.config import Settings
from wanderlens.domain import Asset
from wanderlens.errors import WanderlensError
from wanderlens.library import load_library, read_assets, save_library, write_assets
from wanderlens.pipeline import describe, draft, ingest, set_place, set_publish, set_sale
from wanderlens.publishing import export_posts


def _settings(root: Path) -> Settings:
    vault = root / "vault"
    (vault / "inbox").mkdir(parents=True)
    return Settings(
        vault_dir=vault,
        library_path=root / "library.json",
        exports_dir=root / "exports",
        cache_dir=root / "cache",
        provider="heuristic",
    )


def _write_photo(path: Path, when: str | None, *, gps: bool = False, color=(180, 40, 40)) -> None:
    image = Image.new("RGB", (96, 64), color)
    exif = Image.Exif()
    if when:
        exif[36867] = when
    exif[271] = "SONY"
    exif[272] = "ILCE-7M4"
    if gps:
        gps_ifd = exif.get_ifd(IFD.GPSInfo)
        gps_ifd[1] = "N"
        gps_ifd[2] = (IFDRational(22, 1), IFDRational(17, 1), IFDRational(30, 1))
        gps_ifd[3] = "E"
        gps_ifd[4] = (IFDRational(114, 1), IFDRational(9, 1), IFDRational(15, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", exif=exif, quality=95)


def test_ingest_describe_draft_and_export_keep_location_private(tmp_path: Path):
    settings = _settings(tmp_path)
    inbox = settings.vault_dir / "inbox"
    _write_photo(inbox / "first.jpg", "2024:03:01 10:00:00", gps=True)
    _write_photo(inbox / "second.jpg", "2024:03:02 11:00:00", color=(20, 80, 160))
    (inbox / "second-copy.jpg").write_bytes((inbox / "second.jpg").read_bytes())
    _write_photo(inbox / "later.jpg", "2024:03:08 09:00:00", color=(10, 10, 10))
    (inbox / "notes.txt").write_text("略過", encoding="utf-8")
    (inbox / ".hidden.jpg").write_bytes((inbox / "first.jpg").read_bytes())
    (inbox / "clip.mp4").write_bytes(b"not a real video")

    report = ingest(settings, inbox)
    assert report.scanned_files == 5
    assert report.added == 4
    library = load_library(settings.library_path)
    assets = read_assets(library)
    paths = {asset.relative_path for asset in assets.values()}
    assert "inbox/notes.txt" not in paths
    assert all(not path.startswith("inbox/.") for path in paths)
    second = find_path(assets.values(), "inbox/second.jpg")
    assert asset_paths(second) == {"inbox/second-copy.jpg", "inbox/second.jpg"}
    located = next(asset for asset in assets.values() if asset.gps)
    assert located.gps["lat"] == pytest.approx(22.291667, abs=1e-5)
    assert located.camera_model == "ILCE-7M4"
    assert located.trip_id == second.trip_id
    assert find_path(assets.values(), "inbox/later.jpg").trip_id != located.trip_id

    described = describe(settings)
    assert described.described == 4
    assert described.failed == 0
    again = describe(settings)
    assert again.skipped == 4
    assert again.described == 0

    draft(settings)
    output = export_posts(settings, settings.exports_dir / "posts")
    exported = (output / located.id / "instagram.zh-Hant.md").read_text(encoding="utf-8")
    payload = json.loads((output / located.id / "instagram.zh-Hant.json").read_text(encoding="utf-8"))
    assert "待視覺描述" in exported
    assert "ILCE-7M4" in exported
    assert "needs_human_review" in exported
    assert _contains_key(payload, "gps") is False
    assert _contains_key(payload, "lat") is False
    assert str(located.gps["lat"]) not in exported
    assert str(located.gps["lon"]) not in json.dumps(payload)
    with Image.open(output / located.id / "image.jpg") as public:
        assert not public.getexif().get_ifd(IFD.GPSInfo)
    video = next(asset for asset in read_assets(load_library(settings.library_path)).values() if asset.media_type == "video")
    assert not (output / video.id / "image.jpg").exists()


def test_sale_bundle_requires_clearance_and_no_identifiable_people(tmp_path: Path):
    settings = _settings(tmp_path)
    photo = settings.vault_dir / "inbox" / "scene.jpg"
    _write_photo(photo, "2024:05:01 08:00:00")
    ingest(settings, settings.vault_dir / "inbox")
    describe(settings)
    draft(settings)
    asset = next(iter(read_assets(load_library(settings.library_path)).values()))
    with pytest.raises(WanderlensError):
        set_publish(settings, [asset.id], True)

    data = load_library(settings.library_path)
    assets = read_assets(data)
    assets[asset.id].analysis["semantic"] = {
        "caption_zh_hant": "清晨的海岸。",
        "caption_en": "A coast at dawn.",
        "subjects": ["海岸"],
        "setting": "海岸",
        "mood": "安靜",
        "contains_identifiable_people": False,
        "aesthetic_score": 0.7,
        "suggested_products": ["wallpaper"],
        "sensitive_content": False,
        "quality_notes": "清楚",
    }
    write_assets(data, assets)
    save_library(settings.library_path, data)
    draft(settings)
    set_publish(settings, [asset.id], True)
    exported = export_posts(settings)
    payload = json.loads((exported / asset.id / "xiaohongshu.zh-Hant.json").read_text(encoding="utf-8"))
    assert payload["status"] == "approved_for_manual_publish"
    assert "清晨的海岸" in payload["copy_text"]
    assert "待視覺描述" not in (exported / asset.id / "xiaohongshu.zh-Hant.md").read_text(encoding="utf-8")

    reason = exclusion_reason(
        assets[asset.id],
        min_long_edge=1,
        allow_people=False,
        allow_unknown_people=False,
        allow_sensitive=False,
    )
    assert reason == "not_cleared"
    set_sale(settings, [asset.id], True)
    set_place(settings, asset_ids=[asset.id], trip_id=None, place="未具名海岸")
    bundle = export_bundle(settings, settings.exports_dir / "pack", min_long_edge=1)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "manual_upload_draft"
    assert manifest["included"][0]["user_place"] == "未具名海岸"
    assert _contains_key(manifest, "lat") is False
    assert _contains_key(manifest, "gps") is False
    with Image.open(bundle / "files" / f"{asset.id}.jpg") as public:
        assert not public.getexif().get_ifd(IFD.GPSInfo)

    assets = read_assets(load_library(settings.library_path))
    assets[asset.id].analysis["semantic"]["contains_identifiable_people"] = True
    people = exclusion_reason(
        assets[asset.id],
        min_long_edge=1,
        allow_people=False,
        allow_unknown_people=False,
        allow_sensitive=False,
    )
    assert people == "people_present"
    allowed = exclusion_reason(
        assets[asset.id],
        min_long_edge=1,
        allow_people=True,
        allow_unknown_people=False,
        allow_sensitive=False,
    )
    assert allowed is None


def test_cli_lists_models():
    assert main(["models", "list", "--role", "vision_language", "--commercial", "allowed"]) == 0
    assert main(["models", "show", "qwen3.5-9b"]) == 0


def asset_paths(asset: Asset) -> set[str]:
    return {asset.relative_path, *asset.alternate_paths}


def find_path(assets, relative: str) -> Asset:
    return next(asset for asset in assets if relative in asset_paths(asset))


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        if key in value:
            return True
        return any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False
