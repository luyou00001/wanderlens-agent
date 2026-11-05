from __future__ import annotations

import re

from wanderlens.domain import Asset

PLATFORMS = ("instagram", "xiaohongshu", "x")
LANGUAGES = ("zh-Hant", "en")


def build_drafts(asset: Asset) -> list[dict]:
    semantic = None
    analysis = asset.analysis or {}
    if isinstance(analysis.get("semantic"), dict):
        semantic = analysis["semantic"]
    zh_text, en_text, needs_vision, subjects = _source_text(asset, analysis, semantic)
    drafts = []
    for language in LANGUAGES:
        caption = zh_text if language == "zh-Hant" else en_text
        hashtags = build_hashtags(language, subjects, asset.user_place)
        for platform in PLATFORMS:
            body = _body(caption, asset.user_place, language)
            drafts.append(
                {
                    "platform": platform,
                    "language": language,
                    "title": _title(platform, language, caption, needs_vision),
                    "body": body,
                    "hashtags": hashtags,
                    "copy_text": fit_post(body, hashtags, 280) if platform == "x" else join_post(body, hashtags),
                    "alt_text": clip_text(caption, 300),
                    "needs_vision_model": needs_vision,
                }
            )
    return drafts


def build_hashtags(language: str, subjects: list[str], place: str | None) -> list[str]:
    seeds = ["旅行攝影" if language == "zh-Hant" else "travelphotography"]
    if place:
        seeds.append(place)
    seeds.extend(subjects[:4])
    tags: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        tag = hashtag(seed)
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
        if len(tags) >= 6:
            break
    return tags


def hashtag(text: str) -> str | None:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", text, flags=re.UNICODE)
    cleaned = cleaned.strip("_")
    if not cleaned:
        return None
    return "#" + cleaned[:24]


def clip_text(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if limit <= 0:
        return ""
    if len(compact) <= limit:
        return compact
    if limit == 1:
        return "…"
    return compact[: limit - 1].rstrip() + "…"


def join_post(body: str, hashtags: list[str]) -> str:
    prose = body.strip()
    if not hashtags:
        return prose
    if not prose:
        return " ".join(hashtags)
    return prose + "\n\n" + " ".join(hashtags)


def fit_post(body: str, hashtags: list[str], limit: int) -> str:
    tags = list(hashtags)
    while tags:
        text = join_post(body, tags)
        if len(text) <= limit:
            return text
        tags.pop()
    return clip_text(body, limit)


def _source_text(asset: Asset, analysis: dict, semantic: dict | None) -> tuple[str, str, bool, list[str]]:
    zh_caption = (semantic or {}).get("caption_zh_hant") or ""
    en_caption = (semantic or {}).get("caption_en") or ""
    if semantic and (zh_caption or en_caption):
        if not zh_caption:
            zh_caption = en_caption
        if not en_caption:
            en_caption = zh_caption
        return zh_caption, en_caption, False, list(semantic.get("subjects") or [])
    if asset.decode_error:
        detail = asset.decode_error
        return (
            f"無法解碼這個檔案：{detail}",
            f"This file could not be decoded: {detail}",
            True,
            [],
        )
    return (
        analysis.get("summary_zh_hant") or "尚無描述。這不是畫面描述。",
        analysis.get("summary_en") or "No description yet. This is not a scene description.",
        True,
        [],
    )


def _body(caption: str, place: str | None, language: str) -> str:
    parts = [caption.strip()]
    if place:
        if language == "zh-Hant":
            parts.append(f"地點標記：{place}")
        else:
            parts.append(f"Place label: {place}")
    return "\n\n".join(part for part in parts if part)


def _title(platform: str, language: str, caption: str, needs_vision: bool) -> str:
    if platform == "x":
        return ""
    if needs_vision:
        base = "待補畫面描述" if language == "zh-Hant" else "Awaiting a visual description"
    else:
        base = _first_sentence(caption)
    limit = 20 if platform == "xiaohongshu" else 80
    return clip_text(base, limit)


def _first_sentence(text: str) -> str:
    compact = " ".join(text.split())
    parts = re.split(r"[。！？!?\n]", compact, maxsplit=1)
    return parts[0].strip() or compact
