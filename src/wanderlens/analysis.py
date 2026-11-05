from __future__ import annotations

from pathlib import Path

from wanderlens.config import Settings
from wanderlens.domain import Asset, now_iso
from wanderlens.media import sample_video_frames
from wanderlens.openai_client import OpenAICompatibleClient
from wanderlens.semantic import merge_frame_semantics


def heuristic_analysis(asset: Asset) -> dict:
    fitness = (asset.technical or {}).get("technical_fitness")
    if asset.decode_error:
        summary_zh = f"技術預檢：檔案無法解碼（{asset.decode_error}）。這不是畫面描述。"
        summary_en = (
            f"Technical precheck: the file could not be decoded ({asset.decode_error}). "
            "This is not a scene description."
        )
        error = asset.decode_error
    elif asset.media_type == "video":
        summary_zh = "技術預檢：這是影片，尚未抽幀，也尚未描述畫面。"
        summary_en = (
            "Technical precheck: this is a video. No frames were sampled and the scene was not described."
        )
        error = None
    else:
        summary_zh = (
            f"技術預檢：{asset.width or '未知'}×{asset.height or '未知'}，"
            f"技術分數 {fitness if fitness is not None else '無'}。這不是畫面描述。"
        )
        summary_en = (
            f"Technical precheck: {asset.width or 'unknown'}×{asset.height or 'unknown'}, "
            f"technical score {fitness if fitness is not None else 'n/a'}. "
            "This is not a scene description."
        )
        error = None
    return _record(
        provider="heuristic",
        model="technical-precheck",
        semantic=None,
        fitness=fitness,
        summary_zh=summary_zh,
        summary_en=summary_en,
        error=error,
    )


def describe_with_client(settings: Settings, asset: Asset, source: Path, client: OpenAICompatibleClient) -> dict:
    fitness = (asset.technical or {}).get("technical_fitness")
    if asset.media_type == "image" and asset.decode_error:
        return _record(
            provider="openai",
            model=settings.openai_model,
            semantic=None,
            fitness=fitness,
            summary_zh=f"無法解碼：{asset.decode_error}",
            summary_en=f"Could not decode: {asset.decode_error}",
            error=asset.decode_error,
        )
    if asset.media_type == "video":
        return _describe_video(settings, asset, source, client, fitness)
    semantic = client.describe_image(source)
    return _from_semantic(settings.openai_model, semantic, fitness)


def _describe_video(
    settings: Settings,
    asset: Asset,
    source: Path,
    client: OpenAICompatibleClient,
    fitness: object,
) -> dict:
    try:
        frames = sample_video_frames(
            source,
            settings.cache_dir / "frames" / asset.id,
            settings.frame_count,
        )
    except RuntimeError as exc:
        return _record(
            provider="openai",
            model=settings.openai_model,
            semantic=None,
            fitness=fitness,
            summary_zh=str(exc),
            summary_en=str(exc),
            error=str(exc),
        )
    semantics = [client.describe_image(frame) for frame in frames]
    semantic = merge_frame_semantics(semantics)
    record = _from_semantic(settings.openai_model, semantic, fitness)
    record["frames"] = len(frames)
    return record


def _from_semantic(model: str, semantic: dict, fitness: object) -> dict:
    return _record(
        provider="openai",
        model=model,
        semantic=semantic,
        fitness=fitness,
        summary_zh=semantic.get("caption_zh_hant") or "",
        summary_en=semantic.get("caption_en") or "",
        error=None,
    )


def _record(
    *,
    provider: str,
    model: str,
    semantic: dict | None,
    fitness: object,
    summary_zh: str,
    summary_en: str,
    error: str | None,
) -> dict:
    return {
        "provider": provider,
        "model": model,
        "created_at": now_iso(),
        "semantic": semantic,
        "technical_fitness": fitness,
        "summary_zh_hant": summary_zh,
        "summary_en": summary_en,
        "error": error,
    }
