from __future__ import annotations

import json
import re

PRODUCTS = ("wallpaper", "carousel", "short_video", "print")
_PRODUCT_SET = set(PRODUCTS)


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型輸出裡沒有 JSON 物件。")
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("模型輸出的 JSON 無法解析。") from exc
    if not isinstance(value, dict):
        raise ValueError("模型輸出不是 JSON 物件。")
    return value


def normalize_semantic(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("模型輸出不是 JSON 物件。")
    source = payload.get("semantic") if isinstance(payload.get("semantic"), dict) else payload
    products: list[str] = []
    raw_products = source.get("suggested_products") or []
    if isinstance(raw_products, str):
        raw_products = [raw_products]
    for item in raw_products:
        name = str(item).strip()
        if name in _PRODUCT_SET and name not in products:
            products.append(name)
    return {
        "caption_zh_hant": _plain(source.get("caption_zh_hant")),
        "caption_en": _plain(source.get("caption_en")),
        "subjects": _subjects(source.get("subjects")),
        "setting": _plain(source.get("setting")),
        "mood": _plain(source.get("mood")),
        "contains_identifiable_people": coerce_bool(source.get("contains_identifiable_people")),
        "aesthetic_score": coerce_score(source.get("aesthetic_score")),
        "suggested_products": products,
        "sensitive_content": coerce_bool(source.get("sensitive_content")),
        "quality_notes": _plain(source.get("quality_notes")),
    }


def merge_frame_semantics(items: list[dict]) -> dict:
    if not items:
        raise ValueError("沒有可合併的畫面描述。")
    captions_zh = [item["caption_zh_hant"] for item in items if item.get("caption_zh_hant")]
    captions_en = [item["caption_en"] for item in items if item.get("caption_en")]
    subjects: list[str] = []
    seen: set[str] = set()
    products: list[str] = []
    notes: list[str] = []
    for item in items:
        for subject in item.get("subjects") or []:
            if subject not in seen:
                seen.add(subject)
                subjects.append(subject)
        for product in item.get("suggested_products") or []:
            if product not in products:
                products.append(product)
        note = item.get("quality_notes") or ""
        if note and note not in notes:
            notes.append(note)
    scores = [
        item["aesthetic_score"]
        for item in items
        if isinstance(item.get("aesthetic_score"), (int, float))
    ]
    return {
        "caption_zh_hant": "\n".join(captions_zh),
        "caption_en": "\n".join(captions_en),
        "subjects": subjects[:12],
        "setting": next((item.get("setting") or "" for item in items if item.get("setting")), ""),
        "mood": next((item.get("mood") or "" for item in items if item.get("mood")), ""),
        "contains_identifiable_people": _merge_bool(
            [item.get("contains_identifiable_people") for item in items]
        ),
        "aesthetic_score": round(sum(scores) / len(scores), 4) if scores else None,
        "suggested_products": products,
        "sensitive_content": _merge_bool([item.get("sensitive_content") for item in items]),
        "quality_notes": "；".join(notes[:4]),
    }


def coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "y", "1"}:
            return True
        if text in {"false", "no", "n", "0"}:
            return False
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def coerce_score(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if 1 < number <= 10:
        number = number / 10
    elif 10 < number <= 100:
        number = number / 100
    return round(max(0.0, min(number, 1.0)), 4)


def _merge_bool(values: list[object]) -> bool | None:
    if any(value is True for value in values):
        return True
    if values and all(value is False for value in values):
        return False
    return None


def _plain(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _subjects(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,，、]", value)
    elif isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(re.split(r"[,，、]", str(item)))
    else:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = " ".join(part.split())
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= 12:
            break
    return result
