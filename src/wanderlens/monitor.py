"""本機監控頁。只送出索引摘要，不送出座標，也不提供素材原檔。"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import socket
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from wanderlens import __version__
from wanderlens.catalog import ROLES, load_catalog, select_models
from wanderlens.config import Settings
from wanderlens.domain import now_iso
from wanderlens.errors import WanderlensError
from wanderlens.library import load_library
from wanderlens.paths import repo_root

_PRIVATE_KEYS = {
    "gps",
    "lat",
    "lon",
    "latitude",
    "longitude",
    "gpslatitude",
    "gpslongitude",
}
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}
_TOKEN_NAME = "wanderlens_ui"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class MonitorServer(ThreadingHTTPServer):
    allow_reuse_address = True


def serve_monitor(settings: Settings, host: str = "127.0.0.1", port: int = 8765, *, lan: bool = False) -> None:
    if port == 0:
        raise WanderlensError("連接埠必須介於 1 與 65535。")
    if lan:
        host = "0.0.0.0"
    token = None if _is_loopback(host) else load_or_create_token(repo_root() / "data" / "monitor.token")
    server = create_server(settings, host, port, access_token=token)
    visible_port = server.server_address[1]
    print(f"電腦：http://127.0.0.1:{visible_port}/")
    print("此頁只讀取本機索引，不提供原始照片，也不顯示座標。按 Ctrl+C 結束。")
    if token:
        addresses = lan_addresses()
        if addresses:
            for address in addresses:
                print(f"iPhone：http://{address}:{visible_port}/?k={token}")
        else:
            print(f"iPhone：http://<這台電腦的區網位址>:{visible_port}/?k={token}")
        print("手機與電腦請連同一個 Wi-Fi。用 iPhone 的 Safari 打開上面的網址，再選加入主畫面。")
        print("網址裡的通行憑證不要轉傳。若要作廢，刪除 data/monitor.token 後重新開啟。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已關閉監控頁。")
    finally:
        server.server_close()


def create_server(
    settings: Settings,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    access_token: str | None = None,
) -> MonitorServer:
    if not isinstance(port, int) or port < 0 or port > 65535:
        raise WanderlensError("連接埠必須介於 1 與 65535。")
    web_root = (repo_root() / "web").resolve()
    if not (web_root / "index.html").is_file():
        raise WanderlensError(f"找不到監控頁：{web_root / 'index.html'}")
    handler = build_handler(settings, web_root)
    try:
        server = MonitorServer((host, port), handler)
    except OSError as exc:
        raise WanderlensError(f"無法在 {host}:{port} 開啟監控頁：{exc}") from exc
    server.access_token = access_token
    return server


def build_handler(settings: Settings, web_root: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def version_string(self) -> str:
            return "WanderlensMonitor"

        def do_HEAD(self) -> None:
            self._head_only = True
            self.do_GET()

        def do_GET(self) -> None:
            try:
                self._route()
            except WanderlensError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception:
                traceback.print_exc()
                self._send_json(500, {"error": "監控頁暫時無法讀取資料。"})

        def do_POST(self) -> None:
            self._send_json(405, {"error": "監控頁只接受讀取。"})

        def _route(self) -> None:
            parsed = urlparse(self.path)
            if not self._allow(parsed):
                return
            path = unquote(parsed.path)
            if path != "/" and path.endswith("/"):
                path = path[:-1] or "/"
            if path.startswith("/api/"):
                self._api(path, parsed.query)
                return
            self._static(path)

        def _allow(self, parsed) -> bool:
            expected = getattr(self.server, "access_token", None)
            if not expected:
                return True
            peer = self.client_address[0] if self.client_address else ""
            params = parse_qs(parsed.query)
            query_token = (params.get("k") or [""])[-1]
            cookie_token = cookie_value(self.headers.get("Cookie"), _TOKEN_NAME)
            header_token = self.headers.get("X-Wanderlens-Key") or ""
            if access_granted(peer, cookie_token, query_token, header_token, expected):
                if _same_token(query_token, expected) or _same_token(header_token, expected):
                    self._set_cookie = expected
                return True
            self._send_denied()
            return False

        def _api(self, path: str, query: str) -> None:
            parts = [part for part in path.split("/") if part]
            if any(part in {".", ".."} for part in parts):
                self._send_json(404, {"error": "沒有這個介面。"})
                return
            params = {key: values[-1] for key, values in parse_qs(query).items() if values}
            if parts == ["api", "status"]:
                self._send_json(200, monitor_status(settings))
                return
            if parts == ["api", "summary"]:
                self._send_json(200, monitor_summary(settings))
                return
            if parts == ["api", "assets"]:
                self._send_json(200, monitor_assets(settings, params))
                return
            if len(parts) == 3 and parts[:2] == ["api", "assets"]:
                payload = monitor_asset(settings, parts[2])
                if payload is None:
                    self._send_json(404, {"error": "索引中沒有這筆素材。"})
                    return
                self._send_json(200, payload)
                return
            if parts == ["api", "models"]:
                try:
                    payload = monitor_models(params)
                except WanderlensError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(200, payload)
                return
            if parts == ["api", "trips"]:
                self._send_json(200, monitor_trips(settings))
                return
            self._send_json(404, {"error": "沒有這個介面。"})

        def _static(self, path: str) -> None:
            relative = "index.html" if path == "/" else path.lstrip("/")
            candidate = _safe_file(web_root, relative)
            if candidate is None:
                self._send_bytes(404, "找不到這個檔案。".encode("utf-8"), "text/plain; charset=utf-8", "no-store")
                return
            content_type = _MIME.get(candidate.suffix.lower(), "application/octet-stream")
            cache = "no-cache" if candidate.suffix.lower() in {".html", ".css", ".js"} else "no-store"
            self._send_bytes(200, candidate.read_bytes(), content_type, cache)

        def _send_json(self, status: int, payload: dict) -> None:
            _reject_private(payload)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, body, "application/json; charset=utf-8", "no-store")

        def _send_bytes(self, status: int, body: bytes, content_type: str, cache: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            cookie = getattr(self, "_set_cookie", None)
            if cookie:
                self.send_header("Set-Cookie", _cookie_header(cookie))
            self.end_headers()
            if not getattr(self, "_head_only", False):
                self.wfile.write(body)

        def _send_denied(self) -> None:
            body = (
                "<!DOCTYPE html><html lang=\"zh-Hant\"><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>Wanderlens</title><p>請使用電腦終端機印出的 iPhone 網址打開。"
                "監控頁不會對區網匿名開放。</p>"
            ).encode("utf-8")
            self._send_bytes(401, body, "text/html; charset=utf-8", "no-store")

    return Handler


def access_granted(peer: str, cookie_token: str, query_token: str, header_token: str, expected: str | None) -> bool:
    if not expected:
        return True
    if _is_loopback(peer):
        return True
    return any(_same_token(presented, expected) for presented in (cookie_token, query_token, header_token))


def load_or_create_token(path: Path) -> str:
    if path.is_file():
        current = path.read_text(encoding="utf-8").strip()
        if _TOKEN_PATTERN.fullmatch(current):
            return current
    token = secrets.token_urlsafe(18)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return token


def lan_addresses() -> list[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))
            address = sock.getsockname()[0]
    except OSError:
        return []
    if not address or _is_loopback(address):
        return []
    return [address]


def cookie_value(header: str | None, name: str) -> str:
    if not header:
        return ""
    for part in header.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key.strip() == name:
            return value.strip()
    return ""


def _cookie_header(token: str) -> str:
    return f"{_TOKEN_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=15552000"


def _same_token(presented: str, expected: str) -> bool:
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented, expected)


def _is_loopback(host: str) -> bool:
    name = (host or "").split("%", 1)[0].strip("[]")
    return name in {"127.0.0.1", "::1", "localhost"} or name.startswith("127.")


def monitor_status(settings: Settings) -> dict:
    _, ready, error = _rows(settings)
    return {
        "service": "wanderlens-monitor",
        "version": __version__,
        "library_ready": ready,
        "library_error": error,
        "library_path": str(settings.library_path),
        "provider": settings.provider,
        "openai_model": settings.openai_model,
        "time": now_iso(),
    }


def monitor_summary(settings: Settings) -> dict:
    rows, ready, error = _rows(settings)
    counts = _counts(rows)
    counts["library_ready"] = ready
    counts["library_error"] = error
    return counts


def monitor_assets(settings: Settings, params: dict) -> dict:
    rows, _ready, error = _rows(settings)
    offset = _bounded_int(params.get("offset"), default=0, upper=100000)
    limit = _bounded_int(params.get("limit"), default=80, upper=300)
    needle = (params.get("q") or "").strip().lower()
    matched = [row for row in _ordered(rows) if not needle or needle in _haystack(row)]
    page = matched[offset : offset + limit]
    return {
        "total": len(matched),
        "offset": offset,
        "limit": limit,
        "library_error": error,
        "assets": [_project_asset(row, detail=False) for row in page],
    }


def monitor_asset(settings: Settings, asset_id: str) -> dict | None:
    if not asset_id or asset_id in {".", ".."} or "/" in asset_id or "\\" in asset_id:
        return None
    rows, _ready, _error = _rows(settings)
    for row in rows:
        if str(row.get("id")) == asset_id:
            return _project_asset(row, detail=True)
    return None


def monitor_models(params: dict | None = None) -> dict:
    params = params or {}
    catalog = load_catalog()
    selected = select_models(
        catalog["models"],
        role=params.get("role") or None,
        commercial=params.get("commercial") or None,
        query=params.get("query") or None,
    )
    return {
        "updated": catalog.get("updated"),
        "total": len(catalog["models"]),
        "count": len(selected),
        "roles": sorted(ROLES),
        "models": selected,
    }


def monitor_trips(settings: Settings) -> dict:
    rows, ready, error = _rows(settings)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        key = str(row.get("trip_id") or "")
        grouped.setdefault(key, []).append(row)
    trips = []
    for key, items in grouped.items():
        times = sorted(str(item.get("captured_at")) for item in items if item.get("captured_at"))
        places = [item.get("user_place") for item in items if isinstance(item.get("user_place"), str) and item.get("user_place")]
        trips.append(
            {
                "id": key or None,
                "assets": len(items),
                "images": sum(1 for item in items if item.get("media_type") == "image"),
                "videos": sum(1 for item in items if item.get("media_type") == "video"),
                "place": places[0] if places else None,
                "captured_from": times[0] if times else None,
                "captured_to": times[-1] if times else None,
            }
        )
    trips.sort(key=lambda item: (item["captured_from"] is None, item["captured_from"] or "", item["id"] or ""))
    return {"library_ready": ready, "library_error": error, "trips": trips}


def _rows(settings: Settings) -> tuple[list[dict], bool, str | None]:
    ready, error = _library_state(settings)
    if not ready:
        return [], False, error
    try:
        data = load_library(settings.library_path)
    except WanderlensError as exc:
        return [], False, str(exc)
    assets = data.get("assets")
    if not isinstance(assets, dict):
        return [], False, "素材索引缺少 assets。"
    rows = []
    for key, value in assets.items():
        if not isinstance(value, dict):
            continue
        row = dict(value)
        row.setdefault("id", str(key))
        rows.append(row)
    return rows, True, None


def _library_state(settings: Settings) -> tuple[bool, str | None]:
    path = settings.library_path
    if not path.is_file():
        return False, "尚未建立索引。請先執行 wanderlens ingest。"
    return True, None


def _counts(rows: list[dict]) -> dict:
    described = sum(1 for row in rows if _is_described(row))
    return {
        "assets": len(rows),
        "images": sum(1 for row in rows if row.get("media_type") == "image"),
        "videos": sum(1 for row in rows if row.get("media_type") == "video"),
        "decode_errors": sum(1 for row in rows if row.get("decode_error")),
        "described": described,
        "needs_vision": len(rows) - described,
        "drafted": sum(1 for row in rows if isinstance(row.get("drafts"), list) and row.get("drafts")),
        "approved": sum(1 for row in rows if row.get("approved_for_publish") is True),
        "cleared": sum(1 for row in rows if row.get("cleared_for_sale") is True),
        "with_gps": sum(1 for row in rows if _has_gps(row)),
        "trips": len({str(row.get("trip_id") or "") for row in rows if row.get("trip_id")}),
    }


def _project_asset(row: dict, *, detail: bool) -> dict:
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    semantic = analysis.get("semantic") if isinstance(analysis.get("semantic"), dict) else {}
    drafts = row.get("drafts") if isinstance(row.get("drafts"), list) else []
    technical = row.get("technical") if isinstance(row.get("technical"), dict) else {}
    payload = {
        "id": row.get("id"),
        "relative_path": row.get("relative_path"),
        "alternate_paths": row.get("alternate_paths") if isinstance(row.get("alternate_paths"), list) else [],
        "media_type": row.get("media_type"),
        "byte_size": row.get("byte_size"),
        "width": row.get("width"),
        "height": row.get("height"),
        "captured_at": row.get("captured_at"),
        "has_gps": _has_gps(row),
        "camera_model": row.get("camera_model"),
        "duration_s": row.get("duration_s"),
        "trip_id": row.get("trip_id"),
        "user_place": row.get("user_place") if isinstance(row.get("user_place"), str) else None,
        "decode_error": row.get("decode_error"),
        "technical_fitness": technical.get("technical_fitness", analysis.get("technical_fitness")),
        "provider": analysis.get("provider"),
        "model": analysis.get("model"),
        "described": _is_described(row),
        "needs_vision": not _is_described(row),
        "people": semantic.get("contains_identifiable_people"),
        "sensitive": semantic.get("sensitive_content"),
        "draft_count": len(drafts),
        "approved_for_publish": row.get("approved_for_publish") is True,
        "cleared_for_sale": row.get("cleared_for_sale") is True,
        "ingested_at": row.get("ingested_at"),
    }
    if detail:
        payload.update(
            {
                "summary_zh_hant": analysis.get("summary_zh_hant"),
                "summary_en": analysis.get("summary_en"),
                "subjects": semantic.get("subjects") if isinstance(semantic.get("subjects"), list) else [],
                "setting": semantic.get("setting") if isinstance(semantic.get("setting"), str) else None,
                "mood": semantic.get("mood") if isinstance(semantic.get("mood"), str) else None,
                "aesthetic_score": semantic.get("aesthetic_score"),
                "suggested_products": semantic.get("suggested_products")
                if isinstance(semantic.get("suggested_products"), list)
                else [],
                "drafts": [_project_draft(item) for item in drafts if isinstance(item, dict)],
            }
        )
    return payload


def _project_draft(item: dict) -> dict:
    return {
        "platform": item.get("platform"),
        "language": item.get("language"),
        "title": item.get("title"),
        "needs_vision_model": bool(item.get("needs_vision_model")),
        "copy_text": item.get("copy_text") if isinstance(item.get("copy_text"), str) else "",
    }


def _is_described(row: dict) -> bool:
    analysis = row.get("analysis")
    if not isinstance(analysis, dict) or analysis.get("error"):
        return False
    return analysis.get("provider") == "openai"


def _has_gps(row: dict) -> bool:
    gps = row.get("gps")
    return isinstance(gps, dict) and bool(gps)


def _ordered(rows: list[dict]) -> list[dict]:
    dated = [row for row in rows if row.get("captured_at")]
    undated = [row for row in rows if not row.get("captured_at")]
    dated.sort(key=lambda row: (str(row.get("captured_at")), str(row.get("id") or "")), reverse=True)
    undated.sort(key=lambda row: str(row.get("id") or ""))
    return dated + undated


def _haystack(row: dict) -> str:
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    parts = [
        row.get("id"),
        row.get("relative_path"),
        row.get("user_place"),
        row.get("trip_id"),
        row.get("camera_model"),
        analysis.get("provider"),
        analysis.get("summary_zh_hant"),
        analysis.get("summary_en"),
    ]
    alternate = row.get("alternate_paths")
    if isinstance(alternate, list):
        parts.extend(alternate)
    return " ".join(str(part) for part in parts if part).lower()


def _bounded_int(value: str | None, *, default: int, upper: int) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise WanderlensError("分頁參數必須是整數。") from exc
    if number < 0 or number > upper:
        raise WanderlensError("分頁參數超出範圍。")
    return number


def _safe_file(web_root: Path, relative: str) -> Path | None:
    if not relative or "\\" in relative or relative.startswith("/"):
        return None
    parts = Path(relative).parts
    if any(part in {".", ".."} or part.startswith(".") for part in parts):
        return None
    candidate = (web_root / relative).resolve()
    if not candidate.is_relative_to(web_root) or not candidate.is_file():
        return None
    return candidate


def _reject_private(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).replace("_", "").lower()
            if str(key).lower() in _PRIVATE_KEYS or normalized in _PRIVATE_KEYS:
                raise WanderlensError("監控回應含有不應送出的座標欄位。")
            _reject_private(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private(item)
