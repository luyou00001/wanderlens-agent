from __future__ import annotations

from pathlib import Path

from wanderlens.errors import WanderlensError


def repo_root() -> Path:
    """由目前目錄或程式碼位置向上尋找倉庫根目錄。"""
    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    seen: set[Path] = set()
    for start in starts:
        for candidate in [start, *start.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            catalog = candidate / "catalog" / "open_source_models.yaml"
            if (candidate / "pyproject.toml").is_file() and catalog.is_file():
                return candidate
    raise WanderlensError(
        "找不到專案根目錄。請在倉庫目錄執行，或在含有 catalog/ 的容器工作目錄執行。"
    )


def prompt_path() -> Path:
    return repo_root() / "config" / "prompts" / "vision_json.txt"


def catalog_path() -> Path:
    return repo_root() / "catalog" / "open_source_models.yaml"
