from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Asset:
    id: str
    relative_path: str
    media_type: str
    byte_size: int
    alternate_paths: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    captured_at: str | None = None
    gps: dict | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    focal_length: str | None = None
    duration_s: float | None = None
    trip_id: str | None = None
    user_place: str | None = None
    decode_error: str | None = None
    technical: dict = field(default_factory=dict)
    analysis: dict | None = None
    drafts: list = field(default_factory=list)
    cleared_for_sale: bool = False
    approved_for_publish: bool = False
    ingested_at: str = ""


def asset_from_dict(data: dict) -> Asset:
    values = {}
    for item in fields(Asset):
        if item.name in data:
            values[item.name] = data[item.name]
        elif item.default_factory is not MISSING:  # type: ignore[misc]
            values[item.name] = item.default_factory()
        elif item.default is not MISSING:
            values[item.name] = item.default
    return Asset(**values)


def asset_to_dict(asset: Asset) -> dict:
    return asdict(asset)


@dataclass
class IngestReport:
    scanned_files: int
    added: int
    updated: int
    unreadable: int
    removed: int
    trips: int
    library_path: str


@dataclass
class DescribeReport:
    described: int
    skipped: int
    failed: int
    failures: list[tuple[str, str]]
    library_path: str
