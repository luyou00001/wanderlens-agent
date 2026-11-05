from __future__ import annotations

import json
from pathlib import Path

from wanderlens.config import Settings
from wanderlens.domain import Asset
from wanderlens.errors import WanderlensError
from wanderlens.library import load_library, read_assets
from wanderlens.media import save_public_jpeg


def export_posts(settings: Settings, output_dir: Path | None = None) -> Path:
    data = load_library(settings.library_path)
    assets = list(read_assets(data).values())
    if any(not asset.drafts for asset in assets):
        raise WanderlensError("還有素材沒有草稿。請先執行 wanderlens draft。")
    output = output_dir or (settings.exports_dir / "posts")
    output.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 待審閱草稿",
        "",
        "這些檔案只供人工確認。確認後請自行貼到社群平台。",
        "程式不會登入帳號，也不會代替你發佈。",
        "",
    ]
    for asset in sorted(assets, key=lambda item: (item.captured_at or "9999", item.relative_path)):
        folder = output / asset.id
        if folder.exists():
            _clear_directory(folder)
        folder.mkdir(parents=True, exist_ok=True)
        public_file = _copy_still(settings, asset, folder)
        for draft in asset.drafts:
            status = review_status(draft, asset.approved_for_publish)
            notes = production_notes(asset)
            warnings = _warnings(asset, draft, public_file is not None)
            payload = {
                "schema_version": 1,
                "status": status,
                "platform": draft["platform"],
                "language": draft["language"],
                "title": draft["title"],
                "body": draft["body"],
                "hashtags": draft["hashtags"],
                "copy_text": draft["copy_text"],
                "alt_text": draft["alt_text"],
                "needs_vision_model": draft["needs_vision_model"],
                "warnings": warnings,
                "production_notes": notes,
                "public_file": public_file.name if public_file else None,
            }
            stem = f"{draft['platform']}.{draft['language']}"
            (folder / f"{stem}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (folder / f"{stem}.md").write_text(
                _markdown(payload, banners(draft, asset.approved_for_publish)),
                encoding="utf-8",
            )
            lines.append(
                f"- `{status}` {draft['platform']} / {draft['language']} "
                f"`{asset.id}` {asset.relative_path}"
            )
    if len(lines) == 5:
        lines.append("這次沒有可匯出的草稿。")
    (output / "REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def review_status(draft: dict, approved: bool) -> str:
    if approved and not draft.get("needs_vision_model"):
        return "approved_for_manual_publish"
    return "needs_human_review"


def banners(draft: dict, approved: bool) -> list[str]:
    lines = []
    if draft.get("needs_vision_model"):
        lines.append("【待視覺描述】此段不是畫面描述，請勿直接發佈。")
    if not approved or draft.get("needs_vision_model"):
        lines.append("【待人工審核】確認內容與權利後，才可自行貼上。")
    return lines


def production_notes(asset: Asset) -> dict:
    analysis = asset.analysis or {}
    semantic = analysis.get("semantic") if isinstance(analysis.get("semantic"), dict) else {}
    return {
        "relative_path": asset.relative_path,
        "trip_id": asset.trip_id,
        "user_place": asset.user_place,
        "width": asset.width,
        "height": asset.height,
        "camera_make": asset.camera_make,
        "camera_model": asset.camera_model,
        "lens_model": asset.lens_model,
        "focal_length": asset.focal_length,
        "technical_fitness": (asset.technical or {}).get("technical_fitness"),
        "description_provider": analysis.get("provider"),
        "description_model": analysis.get("model"),
        "quality_notes": semantic.get("quality_notes") or "",
    }


def _warnings(asset: Asset, draft: dict, copied: bool) -> list[str]:
    warnings = []
    if draft.get("needs_vision_model"):
        warnings.append("尚未取得畫面描述。")
    if not asset.approved_for_publish:
        warnings.append("尚未人工審核。")
    semantic = (asset.analysis or {}).get("semantic") if asset.analysis else None
    people = semantic.get("contains_identifiable_people") if isinstance(semantic, dict) else None
    sensitive = semantic.get("sensitive_content") if isinstance(semantic, dict) else None
    if people is True:
        warnings.append("模型判斷畫面含可辨識人物，公開前請確認同意。")
    elif people is None:
        warnings.append("尚未判斷是否含可辨識人物。")
    if sensitive is True:
        warnings.append("模型標記此畫面可能不適合公開。")
    if copied:
        warnings.append("公開 JPEG 已移除定位資訊。")
    else:
        warnings.append("沒有輸出公開影像檔；原始檔仍只留在素材庫。")
    return warnings


def _markdown(payload: dict, banner_lines: list[str]) -> str:
    notes = payload["production_notes"]
    tags = " ".join(payload["hashtags"]) or "（無）"
    banner = "\n".join(banner_lines)
    banner_block = f"\n{banner}\n" if banner else ""
    title = payload["title"] or "（無）"
    camera = notes.get("camera_model") or "未知"
    place = notes.get("user_place") or "未填"
    return (
        f"# {payload['platform']} / {payload['language']}\n\n"
        f"狀態：{payload['status']}\n"
        f"{banner_block}\n"
        f"## 標題\n\n{title}\n\n"
        f"## 可複製內文\n\n{payload['copy_text']}\n\n"
        f"## 標籤\n\n{tags}\n\n"
        f"## 替代文字\n\n{payload['alt_text']}\n\n"
        f"## 製作筆記\n\n"
        f"- 檔案：{notes.get('relative_path')}\n"
        f"- 行程：{notes.get('trip_id')}\n"
        f"- 地點標記：{place}\n"
        f"- 相機：{camera}\n"
        f"- 描述來源：{notes.get('description_provider')} / {notes.get('description_model')}\n\n"
        "此檔只供人工確認後自行發佈。程式不會登入社群平台。\n"
    )


def _copy_still(settings: Settings, asset: Asset, folder: Path) -> Path | None:
    if asset.media_type != "image" or asset.decode_error:
        return None
    source = settings.vault_dir / asset.relative_path
    destination = folder / "image.jpg"
    try:
        save_public_jpeg(source, destination)
    except Exception:
        return None
    return destination


def _clear_directory(folder: Path) -> None:
    for child in folder.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            _clear_directory(child)
            child.rmdir()
