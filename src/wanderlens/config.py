from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from wanderlens.errors import WanderlensError
from wanderlens.paths import repo_root

PATH_FIELDS = ("vault_dir", "library_path", "exports_dir", "cache_dir")
ENV_FIELDS = {
    "WANDERLENS_PROVIDER": "provider",
    "WANDERLENS_OPENAI_BASE_URL": "openai_base_url",
    "WANDERLENS_OPENAI_MODEL": "openai_model",
    "WANDERLENS_OPENAI_API_KEY": "openai_api_key",
}


@dataclass
class Settings:
    vault_dir: Path
    library_path: Path
    exports_dir: Path
    cache_dir: Path
    provider: str = "heuristic"
    openai_base_url: str = "http://127.0.0.1:8000/v1"
    openai_model: str = "Qwen/Qwen3.5-9B"
    openai_api_key: str = "EMPTY"
    request_timeout_s: float = 180
    vision_max_edge: int = 1280
    send_disable_thinking: bool = True
    trip_gap_hours: int = 72
    trip_distance_km: float = 0
    frame_count: int = 4


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def resolve_settings(
    config_path: Path | None = None,
    overrides: dict | None = None,
) -> Settings:
    root = repo_root()
    load_dotenv(root / ".env")
    selected = config_path
    if selected is None:
        default_file = root / "config" / "settings.yaml"
        if default_file.is_file():
            selected = default_file
    elif not selected.is_file():
        raise WanderlensError(f"找不到設定檔：{selected}")

    raw: dict = {}
    if selected is not None:
        loaded = yaml.safe_load(selected.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise WanderlensError("設定檔的最外層必須是對應表。")
        raw.update(loaded)

    for env_name, field_name in ENV_FIELDS.items():
        if os.environ.get(env_name):
            raw[field_name] = os.environ[env_name]

    for key, value in (overrides or {}).items():
        if value is not None:
            raw[key] = value

    settings = Settings(
        vault_dir=_as_path(raw.get("vault_dir", root / "assets_vault"), root),
        library_path=_as_path(
            raw.get("library_path", root / "data" / "library" / "library.json"),
            root,
        ),
        exports_dir=_as_path(raw.get("exports_dir", root / "data" / "exports"), root),
        cache_dir=_as_path(raw.get("cache_dir", root / "data" / "cache"), root),
        provider=str(raw.get("provider", "heuristic")).strip(),
        openai_base_url=str(raw.get("openai_base_url", "http://127.0.0.1:8000/v1")).strip(),
        openai_model=str(raw.get("openai_model", "Qwen/Qwen3.5-9B")).strip(),
        openai_api_key=str(raw.get("openai_api_key", "EMPTY")),
        request_timeout_s=float(raw.get("request_timeout_s", 180)),
        vision_max_edge=int(raw.get("vision_max_edge", 1280)),
        send_disable_thinking=_as_bool(raw.get("send_disable_thinking", True)),
        trip_gap_hours=int(raw.get("trip_gap_hours", 72)),
        trip_distance_km=float(raw.get("trip_distance_km", 0)),
        frame_count=int(raw.get("frame_count", 4)),
    )
    _validate(settings)
    return settings


def _as_path(value: str | Path, root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _validate(settings: Settings) -> None:
    if settings.provider not in {"heuristic", "openai"}:
        raise WanderlensError("provider 只接受 heuristic 或 openai。")
    if settings.trip_gap_hours < 1:
        raise WanderlensError("trip_gap_hours 必須至少為 1。")
    if settings.trip_distance_km < 0:
        raise WanderlensError("trip_distance_km 不可為負數。")
    if not 1 <= settings.frame_count <= 12:
        raise WanderlensError("frame_count 必須介於 1 與 12。")
    if not 64 <= settings.vision_max_edge <= 4096:
        raise WanderlensError("vision_max_edge 必須介於 64 與 4096。")
    if settings.request_timeout_s <= 0:
        raise WanderlensError("request_timeout_s 必須大於 0。")
