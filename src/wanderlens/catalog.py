from __future__ import annotations

import re

import yaml

from wanderlens.errors import WanderlensError
from wanderlens.paths import catalog_path

ROLES = {
    "vision_language",
    "video_understanding",
    "shot_detection",
    "speech_transcription",
    "image_embedding",
    "text_embedding",
    "aesthetic_quality",
    "image_restoration",
    "image_generation",
    "image_editing",
    "video_generation",
    "matting",
    "text_generation",
    "audio_generation",
    "audio_understanding",
    "ocr",
    "pose",
    "privacy_redaction",
}
KINDS = {"model", "tool", "runtime"}
COMMERCIAL = {"allowed", "disallowed", "conditional", "unknown"}
STATUSES = {"recommended", "alternate", "catalog-only", "restricted"}
APIS = {"openai-chat", "custom", "none"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
STATUS_ORDER = {"recommended": 0, "alternate": 1, "catalog-only": 2, "restricted": 3}


def load_catalog(path=None) -> dict:
    selected = path or catalog_path()
    data = _read_catalog_document(selected)
    if path is None:
        extra_root = selected.parent / "extra"
        if extra_root.is_dir():
            for extra in sorted(extra_root.glob("*.yaml")):
                extra_data = _read_yaml(extra)
                extra_models = extra_data.get("models") if isinstance(extra_data, dict) else None
                if not isinstance(extra_models, list):
                    raise WanderlensError(f"附加清單必須包含 models：{extra}")
                data["models"].extend(extra_models)
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise WanderlensError("模型清單是空的。")
    seen: set[str] = set()
    for model in models:
        _validate_model(model, seen)
    return data


def _read_catalog_document(path) -> dict:
    data = _read_yaml(path)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise WanderlensError("模型清單的版本無法讀取。")
    if not isinstance(data.get("models"), list):
        raise WanderlensError("模型清單缺少 models。")
    return data


def _read_yaml(path) -> dict:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise WanderlensError(f"無法讀取模型清單：{path}") from exc
    if not isinstance(loaded, dict):
        raise WanderlensError(f"模型清單格式不正確：{path}")
    return loaded


def select_models(
    models: list[dict],
    *,
    role: str | None = None,
    commercial: str | None = None,
    query: str | None = None,
) -> list[dict]:
    if role and role not in ROLES:
        raise WanderlensError(f"未知的角色：{role}")
    if commercial and commercial not in COMMERCIAL:
        raise WanderlensError(f"未知的授權分類：{commercial}")
    selected = []
    needle = (query or "").strip().lower()
    for model in models:
        if role and role not in model["roles"]:
            continue
        if commercial and model["commercial_use"] != commercial:
            continue
        if needle:
            haystack = " ".join(
                [
                    model["id"],
                    model["name"],
                    model.get("huggingface") or "",
                    model.get("github") or "",
                    " ".join(model["roles"]),
                    model.get("notes") or "",
                ]
            ).lower()
            if needle not in haystack:
                continue
        selected.append(model)
    selected.sort(key=lambda item: (STATUS_ORDER.get(item["status"], 9), item["id"]))
    return selected


def find_model(models: list[dict], model_id: str) -> dict:
    for model in models:
        if model["id"] == model_id:
            return model
    known = "、".join(model["id"] for model in models[:8])
    raise WanderlensError(f"清單中沒有 {model_id}。例如：{known}")


def _validate_model(model: object, seen: set[str]) -> None:
    if not isinstance(model, dict):
        raise WanderlensError("模型清單含有無法讀取的項目。")
    model_id = model.get("id")
    if not isinstance(model_id, str) or not ID_PATTERN.match(model_id):
        raise WanderlensError(f"模型識別碼不合法：{model_id!r}")
    if model_id in seen:
        raise WanderlensError(f"模型識別碼重複：{model_id}")
    seen.add(model_id)
    for key in ("name", "kind", "license", "commercial_use", "status", "server_api", "notes"):
        if not isinstance(model.get(key), str) or not str(model.get(key)).strip():
            raise WanderlensError(f"{model_id} 缺少 {key}。")
    if model["kind"] not in KINDS:
        raise WanderlensError(f"{model_id} 的 kind 不正確。")
    if model["commercial_use"] not in COMMERCIAL:
        raise WanderlensError(f"{model_id} 的 commercial_use 不正確。")
    if model["status"] not in STATUSES:
        raise WanderlensError(f"{model_id} 的 status 不正確。")
    if model["server_api"] not in APIS:
        raise WanderlensError(f"{model_id} 的 server_api 不正確。")
    roles = model.get("roles")
    if not isinstance(roles, list) or not roles or any(role not in ROLES for role in roles):
        raise WanderlensError(f"{model_id} 的 roles 不正確。")
    links = [model.get("huggingface"), model.get("github"), model.get("weights")]
    if not any(isinstance(link, str) and link.strip() for link in links):
        raise WanderlensError(f"{model_id} 至少要有 Hugging Face、GitHub 或權重連結。")
    if model["status"] in {"recommended", "alternate"} and model["commercial_use"] != "allowed":
        raise WanderlensError(f"{model_id} 被列為建議項目，但授權不是 allowed。")
    if model["status"] == "recommended" and model["server_api"] != "openai-chat":
        raise WanderlensError(f"{model_id} 被列為預設建議，但目前的描述流程還接不上它。")
    if model["status"] == "restricted" and model["commercial_use"] == "allowed":
        raise WanderlensError(f"{model_id} 標成 restricted，授權卻是 allowed。")
