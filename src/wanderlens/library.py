from __future__ import annotations

import json
from pathlib import Path

from wanderlens.domain import Asset, asset_from_dict, asset_to_dict
from wanderlens.errors import WanderlensError


def empty_library() -> dict:
    return {"schema_version": 1, "assets": {}}


def load_library(path: Path) -> dict:
    if not path.is_file():
        raise WanderlensError(f"找不到素材索引：{path}。請先執行 wanderlens ingest。")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WanderlensError(f"素材索引不是有效的 JSON：{path}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise WanderlensError("無法讀取這個版本的素材索引。")
    assets = data.get("assets")
    if not isinstance(assets, dict):
        raise WanderlensError("素材索引缺少 assets。")
    return data


def save_library(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_assets(data: dict) -> dict[str, Asset]:
    return {key: asset_from_dict(value) for key, value in data["assets"].items()}


def write_assets(data: dict, assets: dict[str, Asset]) -> None:
    data["assets"] = {key: asset_to_dict(asset) for key, asset in assets.items()}
