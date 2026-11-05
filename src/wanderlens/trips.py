from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from wanderlens.domain import Asset


def assign_trips(assets: list[Asset], gap_hours_limit: int, distance_km: float) -> int:
    """以拍攝時間把素材分成行程。座標只在設定了距離門檻時用來切開，不會變成地名。"""
    for asset in assets:
        asset.trip_id = None
    dated = sorted(
        (asset for asset in assets if asset.captured_at),
        key=lambda asset: (asset.captured_at or "", asset.id),
    )
    clusters: list[list[Asset]] = []
    for asset in dated:
        if not clusters or _split(clusters[-1][-1], asset, gap_hours_limit, distance_km):
            clusters.append([asset])
        else:
            clusters[-1].append(asset)
    for cluster in clusters:
        earliest = min(cluster, key=lambda asset: (asset.captured_at or "", asset.id))
        trip_id = "trip-" + earliest.id[:12]
        for asset in cluster:
            asset.trip_id = trip_id
    undated = False
    for asset in assets:
        if asset.trip_id is None:
            asset.trip_id = "trip-undated"
            undated = True
    return len(clusters) + (1 if undated else 0)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    area = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return 2 * radius * asin(min(1.0, sqrt(area)))


def _split(previous: Asset, current: Asset, gap_hours_limit: int, distance_km: float) -> bool:
    if _gap_hours(previous.captured_at or "", current.captured_at or "") > gap_hours_limit:
        return True
    if distance_km > 0 and previous.gps and current.gps:
        distance = haversine_km(
            previous.gps["lat"],
            previous.gps["lon"],
            current.gps["lat"],
            current.gps["lon"],
        )
        if distance > distance_km:
            return True
    return False


def _gap_hours(earlier: str, later: str) -> float:
    from datetime import datetime

    start = datetime.fromisoformat(earlier)
    end = datetime.fromisoformat(later)
    return (end - start).total_seconds() / 3600
