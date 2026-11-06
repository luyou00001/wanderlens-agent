"""給沒有本機索引的預覽頁使用的假資料。不得包含座標。"""

from __future__ import annotations

import json
from pathlib import Path

from wanderlens import __version__
from wanderlens.catalog import ROLES, load_catalog, select_models

NOTICE = "這是預覽版面，不是你的素材庫。照片索引只留在執行 wanderlens ui 的那台機器。"
_PRIVATE_KEYS = {"gps", "lat", "lon", "latitude", "longitude", "gpslatitude", "gpslongitude"}


def build_preview() -> dict:
    catalog = load_catalog()
    models = select_models(catalog["models"])
    assets = _sample_assets()
    payload = {
        "preview": True,
        "notice": NOTICE,
        "status": {
            "service": "wanderlens-preview",
            "version": __version__,
            "library_ready": False,
            "library_error": None,
            "library_path": "預覽資料，不是本機索引",
            "provider": "preview",
            "openai_model": "",
            "time": None,
        },
        "summary": _summary(assets),
        "assets": assets,
        "models": models,
        "roles": sorted(ROLES),
        "trips": [
            {
                "id": "preview-trip",
                "assets": 2,
                "images": 1,
                "videos": 1,
                "place": "預覽地點",
                "captured_from": "2024-04-02T09:30:00+00:00",
                "captured_to": "2024-04-02T11:05:00+00:00",
            }
        ],
        "updated": catalog.get("updated"),
    }
    _reject_private(payload)
    return payload


def write_preview(path: Path) -> dict:
    payload = build_preview()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _sample_assets() -> list[dict]:
    return [
        {
            "id": "preview-photo",
            "relative_path": "preview/shore.jpg",
            "alternate_paths": [],
            "media_type": "image",
            "byte_size": 1800000,
            "width": 3000,
            "height": 2000,
            "captured_at": "2024-04-02T09:30:00+00:00",
            "has_gps": True,
            "camera_model": "預覽機身",
            "duration_s": None,
            "trip_id": "preview-trip",
            "user_place": "預覽地點",
            "decode_error": None,
            "technical_fitness": 80,
            "provider": "openai",
            "model": "預覽模型",
            "described": True,
            "needs_vision": False,
            "people": False,
            "sensitive": False,
            "draft_count": 1,
            "approved_for_publish": False,
            "cleared_for_sale": True,
            "ingested_at": "2024-04-03T00:00:00+00:00",
            "summary_zh_hant": "這是預覽用的畫面說明，不是你的照片。",
            "summary_en": "Preview caption. This is not your photograph.",
            "subjects": ["岸"],
            "setting": "預覽場景",
            "mood": "平靜",
            "aesthetic_score": 0.7,
            "suggested_products": ["wallpaper"],
            "drafts": [
                {
                    "platform": "instagram",
                    "language": "zh-Hant",
                    "title": "預覽草稿",
                    "needs_vision_model": False,
                    "copy_text": "預覽草稿，不是你的貼文。",
                }
            ],
        },
        {
            "id": "preview-video",
            "relative_path": "preview/walk.mp4",
            "alternate_paths": [],
            "media_type": "video",
            "byte_size": 12000000,
            "width": 1920,
            "height": 1080,
            "captured_at": "2024-04-02T11:05:00+00:00",
            "has_gps": False,
            "camera_model": None,
            "duration_s": 8.0,
            "trip_id": "preview-trip",
            "user_place": None,
            "decode_error": None,
            "technical_fitness": None,
            "provider": "heuristic",
            "model": "technical-precheck",
            "described": False,
            "needs_vision": True,
            "people": None,
            "sensitive": None,
            "draft_count": 0,
            "approved_for_publish": False,
            "cleared_for_sale": False,
            "ingested_at": "2024-04-03T00:00:00+00:00",
            "summary_zh_hant": "技術預檢：這是預覽影片，尚未描述畫面。",
            "summary_en": "Technical precheck: preview video, scene not described.",
            "subjects": [],
            "setting": None,
            "mood": None,
            "aesthetic_score": None,
            "suggested_products": [],
            "drafts": [],
        },
    ]


def _summary(assets: list[dict]) -> dict:
    described = sum(1 for asset in assets if asset["described"])
    return {
        "assets": len(assets),
        "images": sum(1 for asset in assets if asset["media_type"] == "image"),
        "videos": sum(1 for asset in assets if asset["media_type"] == "video"),
        "decode_errors": 0,
        "described": described,
        "needs_vision": len(assets) - described,
        "drafted": sum(1 for asset in assets if asset["draft_count"]),
        "approved": 0,
        "cleared": sum(1 for asset in assets if asset["cleared_for_sale"]),
        "with_gps": sum(1 for asset in assets if asset["has_gps"]),
        "trips": 1,
        "library_ready": False,
        "library_error": None,
    }


def _reject_private(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).replace("_", "").lower()
            if str(key).lower() in _PRIVATE_KEYS or normalized in _PRIVATE_KEYS:
                raise RuntimeError(f"預覽資料含有不應出現的欄位：{key}")
            _reject_private(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private(item)
