from __future__ import annotations

import os
from pathlib import Path

from wanderlens.analysis import describe_with_client, heuristic_analysis
from wanderlens.config import Settings
from wanderlens.domain import Asset, DescribeReport, IngestReport, now_iso
from wanderlens.drafts import build_drafts
from wanderlens.errors import WanderlensError
from wanderlens.library import empty_library, load_library, read_assets, save_library, write_assets
from wanderlens.media import content_id, file_mtime, inspect_image, media_type_for, probe_video
from wanderlens.openai_client import OpenAICompatibleClient
from wanderlens.trips import assign_trips


def ingest(settings: Settings, input_dir: Path | None = None, prune: bool = False) -> IngestReport:
    vault = settings.vault_dir
    if not vault.is_dir():
        raise WanderlensError(f"找不到素材庫：{vault}")
    scan_root = _scan_root(vault, input_dir)
    if settings.library_path.is_file():
        data = load_library(settings.library_path)
    else:
        data = empty_library()
    assets = read_assets(data)
    scanned, observed, unreadable = _scan(vault, scan_root)
    added = 0
    updated = 0
    seen_ids: set[str] = set()
    for asset_id, observed_asset in observed.items():
        seen_ids.add(asset_id)
        previous = assets.get(asset_id)
        if previous is None:
            observed_asset.ingested_at = now_iso()
            added += 1
        else:
            observed_asset.analysis = previous.analysis
            observed_asset.drafts = previous.drafts
            observed_asset.cleared_for_sale = previous.cleared_for_sale
            observed_asset.approved_for_publish = previous.approved_for_publish
            observed_asset.user_place = previous.user_place
            observed_asset.ingested_at = previous.ingested_at or now_iso()
            updated += 1
        assets[asset_id] = observed_asset
    removed = 0
    if prune:
        removed = _prune(assets, vault, scan_root, seen_ids)
    trips = assign_trips(list(assets.values()), settings.trip_gap_hours, settings.trip_distance_km)
    write_assets(data, assets)
    save_library(settings.library_path, data)
    return IngestReport(
        scanned_files=scanned,
        added=added,
        updated=updated,
        unreadable=unreadable,
        removed=removed,
        trips=trips,
        library_path=str(settings.library_path),
    )


def describe(settings: Settings, force: bool = False, limit: int | None = None) -> DescribeReport:
    data = load_library(settings.library_path)
    assets = read_assets(data)
    ordered = sorted(assets.values(), key=_describe_order)
    pending = [asset for asset in ordered if force or not _has_fresh_analysis(asset)]
    if limit is not None:
        pending = pending[:limit]
    client = None
    if settings.provider == "openai" and pending:
        client = OpenAICompatibleClient(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout=settings.request_timeout_s,
            max_edge=settings.vision_max_edge,
            send_disable_thinking=settings.send_disable_thinking,
        )
    described = 0
    failed = 0
    failures: list[tuple[str, str]] = []
    for asset in pending:
        source = settings.vault_dir / asset.relative_path
        try:
            if not source.is_file():
                raise FileNotFoundError(f"找不到檔案：{asset.relative_path}")
            if settings.provider == "heuristic":
                analysis = heuristic_analysis(asset)
            elif client is None:
                raise WanderlensError("沒有可用的模型客戶端。")
            else:
                analysis = describe_with_client(settings, asset, source, client)
        except Exception as exc:
            analysis = heuristic_analysis(asset)
            analysis["provider"] = settings.provider
            analysis["model"] = settings.openai_model if settings.provider == "openai" else analysis["model"]
            analysis["error"] = str(exc)
            analysis["semantic"] = None
            analysis["summary_zh_hant"] = str(exc)
            analysis["summary_en"] = str(exc)
        asset.analysis = analysis
        asset.drafts = []
        asset.approved_for_publish = False
        if analysis.get("error"):
            failed += 1
            failures.append((asset.relative_path, str(analysis["error"])))
        else:
            described += 1
    write_assets(data, assets)
    save_library(settings.library_path, data)
    return DescribeReport(
        described=described,
        skipped=len(ordered) - len(pending),
        failed=failed,
        failures=failures,
        library_path=str(settings.library_path),
    )


def draft(settings: Settings) -> int:
    data = load_library(settings.library_path)
    assets = read_assets(data)
    if not assets:
        raise WanderlensError("素材索引是空的。請先放入照片並執行 ingest。")
    missing = [asset.relative_path for asset in assets.values() if not asset.analysis]
    if missing:
        sample = "、".join(missing[:5])
        raise WanderlensError(f"還有素材尚未描述，請先執行 describe：{sample}")
    changed_assets = 0
    for asset in assets.values():
        new_drafts = build_drafts(asset)
        if new_drafts != asset.drafts:
            asset.drafts = new_drafts
            asset.approved_for_publish = False
            changed_assets += 1
        else:
            asset.drafts = new_drafts
    write_assets(data, assets)
    save_library(settings.library_path, data)
    return changed_assets


def set_sale(settings: Settings, asset_ids: list[str], cleared: bool) -> int:
    return _update_assets(settings, asset_ids, "cleared_for_sale", cleared)


def set_publish(settings: Settings, asset_ids: list[str], approved: bool) -> int:
    assets = _load_for_update(settings)
    missing = [asset_id for asset_id in asset_ids if asset_id not in assets]
    if missing:
        raise WanderlensError("找不到素材：" + "、".join(missing))
    for asset_id in asset_ids:
        asset = assets[asset_id]
        if approved and not asset.drafts:
            raise WanderlensError(f"{asset.relative_path} 還沒有草稿，請先執行 draft。")
        if approved and any(item.get("needs_vision_model") for item in asset.drafts):
            raise WanderlensError(
                f"{asset.relative_path} 還沒有畫面描述，不能標記為可發佈。"
            )
        asset.approved_for_publish = approved
    _save_loaded(settings, assets)
    return len(asset_ids)


def set_place(
    settings: Settings,
    *,
    asset_ids: list[str] | None,
    trip_id: str | None,
    place: str | None,
) -> int:
    assets = _load_for_update(settings)
    selected: list[Asset]
    if trip_id:
        selected = [asset for asset in assets.values() if asset.trip_id == trip_id]
        if not selected:
            raise WanderlensError(f"找不到行程：{trip_id}")
    else:
        ids = asset_ids or []
        missing = [asset_id for asset_id in ids if asset_id not in assets]
        if missing or not ids:
            raise WanderlensError("找不到素材：" + "、".join(missing or ["未指定"]))
        selected = [assets[asset_id] for asset_id in ids]
    for asset in selected:
        asset.user_place = place
    _save_loaded(settings, assets)
    return len(selected)


def iter_assets(settings: Settings) -> list[Asset]:
    data = load_library(settings.library_path)
    assets = read_assets(data)
    return sorted(assets.values(), key=lambda asset: (asset.captured_at or "9999", asset.relative_path))


def _update_assets(settings: Settings, asset_ids: list[str], field_name: str, value: bool) -> int:
    assets = _load_for_update(settings)
    missing = [asset_id for asset_id in asset_ids if asset_id not in assets]
    if missing:
        raise WanderlensError("找不到素材：" + "、".join(missing))
    for asset_id in asset_ids:
        setattr(assets[asset_id], field_name, value)
    _save_loaded(settings, assets)
    return len(asset_ids)


def _load_for_update(settings: Settings) -> dict[str, Asset]:
    return read_assets(load_library(settings.library_path))


def _save_loaded(settings: Settings, assets: dict[str, Asset]) -> None:
    data = load_library(settings.library_path)
    write_assets(data, assets)
    save_library(settings.library_path, data)


def _scan(vault: Path, scan_root: Path) -> tuple[int, dict[str, Asset], int]:
    observed: dict[str, Asset] = {}
    scanned = 0
    unreadable = 0
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith(".") or name == ".gitkeep":
                continue
            path = Path(dirpath) / name
            kind = media_type_for(path)
            if kind is None or not path.is_file():
                continue
            scanned += 1
            try:
                relative = path.relative_to(vault).as_posix()
                asset_id = content_id(path)
            except OSError:
                unreadable += 1
                continue
            current = observed.get(asset_id)
            if current is None:
                observed[asset_id] = _new_asset(asset_id, relative, kind, path)
            elif relative != current.relative_path and relative not in current.alternate_paths:
                current.alternate_paths.append(relative)
    for asset in observed.values():
        paths = sorted({asset.relative_path, *asset.alternate_paths})
        asset.relative_path = paths[0]
        asset.alternate_paths = paths[1:]
    return scanned, observed, unreadable


def _new_asset(asset_id: str, relative: str, kind: str, path: Path) -> Asset:
    asset = Asset(
        id=asset_id,
        relative_path=relative,
        media_type=kind,
        byte_size=path.stat().st_size,
        technical={"file_mtime": file_mtime(path)},
    )
    if kind == "image":
        info = inspect_image(path)
        asset.decode_error = info.get("decode_error")
        asset.width = info.get("width")
        asset.height = info.get("height")
        asset.captured_at = info.get("captured_at")
        asset.gps = info.get("gps")
        asset.camera_make = info.get("camera_make")
        asset.camera_model = info.get("camera_model")
        asset.lens_model = info.get("lens_model")
        asset.focal_length = info.get("focal_length")
        if info.get("technical"):
            asset.technical.update(info["technical"])
    else:
        info = probe_video(path)
        asset.width = info.get("width")
        asset.height = info.get("height")
        asset.duration_s = info.get("duration_s")
    return asset


def _prune(assets: dict[str, Asset], vault: Path, scan_root: Path, seen_ids: set[str]) -> int:
    prefix = scan_root.relative_to(vault).as_posix()
    if prefix == ".":
        prefix = ""
    removed = 0
    for asset_id in list(assets):
        asset = assets[asset_id]
        paths = [asset.relative_path, *asset.alternate_paths]
        if not any(_under(path, prefix) for path in paths):
            continue
        if asset_id in seen_ids:
            continue
        del assets[asset_id]
        removed += 1
    return removed


def _under(relative: str, prefix: str) -> bool:
    if not prefix:
        return True
    return relative == prefix or relative.startswith(prefix + "/")


def _scan_root(vault: Path, input_dir: Path | None) -> Path:
    if input_dir is None:
        inbox = vault / "inbox"
        scan_root = inbox if inbox.is_dir() else vault
    else:
        scan_root = input_dir
    if not scan_root.is_dir():
        raise WanderlensError(f"找不到掃描目錄：{scan_root}")
    try:
        scan_root.relative_to(vault)
    except ValueError as exc:
        raise WanderlensError("掃描目錄必須位於素材庫之內。") from exc
    return scan_root


def _describe_order(asset: Asset) -> tuple:
    return (asset.media_type != "image", asset.captured_at or "9999", asset.relative_path)


def _has_fresh_analysis(asset: Asset) -> bool:
    return bool(asset.analysis) and not asset.analysis.get("error")
