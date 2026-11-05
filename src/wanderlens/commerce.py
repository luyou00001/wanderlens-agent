from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from wanderlens.config import Settings
from wanderlens.domain import Asset
from wanderlens.library import load_library, read_assets
from wanderlens.media import save_public_jpeg


def exclusion_reason(
    asset: Asset,
    *,
    min_long_edge: int,
    allow_people: bool,
    allow_unknown_people: bool,
    allow_sensitive: bool,
) -> str | None:
    if asset.media_type != "image":
        return "not_image"
    if asset.decode_error:
        return "decode_error"
    edge = max(asset.width or 0, asset.height or 0)
    if edge < min_long_edge:
        return "below_min_edge"
    if not asset.cleared_for_sale:
        return "not_cleared"
    semantic = (asset.analysis or {}).get("semantic") if asset.analysis else None
    if not isinstance(semantic, dict):
        semantic = {}
    if semantic.get("sensitive_content") is True and not allow_sensitive:
        return "sensitive_content"
    people = semantic.get("contains_identifiable_people")
    if people is True:
        return None if allow_people else "people_present"
    if people is False:
        return None
    return None if allow_unknown_people else "people_unknown"


def export_bundle(
    settings: Settings,
    output_dir: Path | None = None,
    *,
    min_long_edge: int = 1600,
    allow_people: bool = False,
    allow_unknown_people: bool = False,
    allow_sensitive: bool = False,
) -> Path:
    data = load_library(settings.library_path)
    assets = sorted(
        read_assets(data).values(),
        key=lambda asset: (asset.trip_id or "", asset.captured_at or "9999", asset.relative_path),
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = output_dir or (settings.exports_dir / "products" / stamp)
    files = root / "files"
    included = []
    excluded = []
    for asset in assets:
        reason = exclusion_reason(
            asset,
            min_long_edge=min_long_edge,
            allow_people=allow_people,
            allow_unknown_people=allow_unknown_people,
            allow_sensitive=allow_sensitive,
        )
        if reason:
            excluded.append(
                {
                    "asset_id": asset.id,
                    "relative_path": asset.relative_path,
                    "reason": reason,
                }
            )
            continue
        destination = files / f"{asset.id}.jpg"
        try:
            save_public_jpeg(settings.vault_dir / asset.relative_path, destination)
        except Exception as exc:
            excluded.append(
                {
                    "asset_id": asset.id,
                    "relative_path": asset.relative_path,
                    "reason": f"export_failed:{exc}",
                }
            )
            continue
        included.append(
            {
                "asset_id": asset.id,
                "relative_path": asset.relative_path,
                "width": asset.width,
                "height": asset.height,
                "user_place": asset.user_place,
                "file": destination.relative_to(root).as_posix(),
            }
        )
    manifest = {
        "schema_version": 1,
        "status": "manual_upload_draft" if included else "empty_pending_review",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "min_long_edge": min_long_edge,
        "included": included,
        "excluded": excluded,
        "notes": [
            "這是尚未上架的草稿包。",
            "複製出的 JPEG 已移除 EXIF，包含定位資訊。",
            "請自行確認著作權、人物同意與模型授權後，再上傳到你的商店。",
            "若影像經過超解析度放大，銷售頁必須如實說明。",
        ],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(_readme(manifest), encoding="utf-8")
    return root


def _readme(manifest: dict) -> str:
    return (
        "# 數位影像草稿包\n\n"
        f"狀態：{manifest['status']}\n\n"
        f"收入 {len(manifest['included'])} 張，排除 {len(manifest['excluded'])} 張。\n\n"
        "此目錄不會自動上傳。請先閱讀 manifest.json 的排除原因，\n"
        "確認你擁有販售這些影像的權利，再自行上傳到商店。\n"
    )
