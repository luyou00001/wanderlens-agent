from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from PIL.ExifTags import IFD

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def media_type_for(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return None


def content_id(path: Path) -> str:
    digest = hashlib.sha256()
    size = path.stat().st_size
    digest.update(size.to_bytes(8, "big"))
    with path.open("rb") as handle:
        digest.update(handle.read(1024 * 1024))
        if size > 1024 * 1024:
            handle.seek(max(size - 1024 * 1024, 0))
            digest.update(handle.read(1024 * 1024))
    return digest.hexdigest()[:16]


def file_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()


def technical_fitness(width: int, height: int, mean_luma: float, contrast: float) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    megapixels = (width * height) / 1_000_000
    resolution = min(megapixels / 8.0, 1.0)
    aspect = width / height
    if aspect >= 1.2:
        orientation = 1.0
    elif aspect >= 0.8:
        orientation = 0.7
    else:
        orientation = 0.5
    luma_score = 1.0 - min(abs(mean_luma - 140) / 140, 1.0)
    contrast_score = min(contrast / 50.0, 1.0)
    score = 0.35 * resolution + 0.25 * orientation + 0.2 * luma_score + 0.2 * contrast_score
    return round(max(0.0, min(score, 1.0)), 4)


def measure_image(image: Image.Image) -> dict:
    width, height = image.size
    sample = image.convert("RGB")
    sample.thumbnail((64, 64))
    pixels = list(sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata())
    if not pixels:
        return {"mean_luma": 0.0, "contrast": 0.0, "technical_fitness": 0.0}
    lumas = [0.2126 * red + 0.7152 * green + 0.0722 * blue for red, green, blue in pixels]
    mean = sum(lumas) / len(lumas)
    variance = sum((value - mean) ** 2 for value in lumas) / len(lumas)
    contrast = variance**0.5
    return {
        "mean_luma": round(mean, 2),
        "contrast": round(contrast, 2),
        "technical_fitness": technical_fitness(width, height, mean, contrast),
    }


def inspect_image(path: Path) -> dict:
    try:
        with Image.open(path) as image:
            captured_at, gps, camera = read_exif(image)
            oriented = ImageOps.exif_transpose(image)
            stats = measure_image(oriented)
            width, height = oriented.size
    except Exception as exc:  # Pillow 對損毀檔與不支援格式都會丟出不同例外。
        return {"decode_error": str(exc)}
    return {
        "width": width,
        "height": height,
        "captured_at": captured_at,
        "gps": gps,
        "camera_make": camera.get("make"),
        "camera_model": camera.get("model"),
        "lens_model": camera.get("lens"),
        "focal_length": camera.get("focal_length"),
        "technical": stats,
    }


def read_exif(image: Image.Image) -> tuple[str | None, dict | None, dict]:
    camera = {"make": None, "model": None, "lens": None, "focal_length": None}
    try:
        exif = image.getexif()
    except Exception:
        return None, None, camera
    if not exif:
        return None, None, camera
    captured_at = _captured_at(exif.get(36867) or exif.get(306))
    camera["make"] = _text(exif.get(271))
    camera["model"] = _text(exif.get(272))
    camera["lens"] = _text(exif.get(42036))
    camera["focal_length"] = _text(exif.get(37386))
    gps = None
    try:
        gps_ifd = exif.get_ifd(IFD.GPSInfo)
    except Exception:
        gps_ifd = None
    if gps_ifd:
        gps = _gps(gps_ifd)
    return captured_at, gps, camera


def save_public_jpeg(source: Path, destination: Path, quality: int = 92) -> None:
    """另存一份不含 EXIF 的 JPEG。定位資訊不會被複製。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(destination, format="JPEG", quality=quality, optimize=True)


def probe_video(path: Path) -> dict:
    if shutil.which("ffprobe") is None:
        return {}
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if completed.returncode != 0:
        return {}
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    info: dict = {}
    streams = payload.get("streams") or []
    if streams:
        width = streams[0].get("width")
        height = streams[0].get("height")
        if isinstance(width, int) and isinstance(height, int):
            info["width"] = width
            info["height"] = height
    duration = (payload.get("format") or {}).get("duration")
    if duration is not None:
        try:
            info["duration_s"] = round(float(duration), 3)
        except (TypeError, ValueError):
            pass
    return info


def frame_timestamps(duration_s: float | None, count: int) -> list[float]:
    count = max(1, count)
    if duration_s is None or duration_s <= 0:
        return [0.5]
    if count == 1:
        return [min(1.0, max(duration_s * 0.5, 0.0))]
    last = max(duration_s - 0.25, 0.0)
    if last <= 0.1:
        return [0.0]
    step = (last - 0.1) / (count - 1)
    return [round(0.1 + step * index, 3) for index in range(count)]


def sample_video_frames(video: Path, destination: Path, count: int) -> list[Path]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("需要 ffmpeg 與 ffprobe 才能為影片抽幀。")
    info = probe_video(video)
    timestamps = frame_timestamps(info.get("duration_s"), count)
    destination.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for index, timestamp in enumerate(timestamps):
        target = destination / f"frame-{index:02d}.jpg"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(target),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode == 0 and target.is_file():
            frames.append(target)
    if not frames:
        raise RuntimeError("ffmpeg 沒有抽出任何畫面。")
    return frames


def jpeg_data_url(path: Path, max_edge: int) -> str:
    import base64
    import io

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image.thumbnail((max_edge, max_edge))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        text = value.decode("utf-8", "ignore").strip("\x00").strip()
    else:
        text = str(value).strip()
    return text or None


def _captured_at(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def _ratio(value: object) -> float:
    if isinstance(value, tuple):
        numerator, denominator = value
        denominator = float(denominator)
        return float(numerator) / denominator if denominator else 0.0
    return float(value)


def _dms(value: object) -> float:
    if not isinstance(value, (tuple, list)) or len(value) < 3:
        raise ValueError("GPS 座標格式不完整。")
    return _ratio(value[0]) + _ratio(value[1]) / 60 + _ratio(value[2]) / 3600


def _gps(gps_ifd: dict) -> dict | None:
    try:
        latitude_raw = gps_ifd.get(2)
        longitude_raw = gps_ifd.get(4)
        if not latitude_raw or not longitude_raw:
            return None
        latitude = _dms(latitude_raw)
        longitude = _dms(longitude_raw)
        if _text(gps_ifd.get(1)) in {"S", "s"}:
            latitude = -abs(latitude)
        if _text(gps_ifd.get(3)) in {"W", "w"}:
            longitude = -abs(longitude)
        return {"lat": round(latitude, 6), "lon": round(longitude, 6)}
    except Exception:
        return None
