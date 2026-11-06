#!/usr/bin/env python3
"""確認即將公開的網站只含預覽介面。

這個網址會對整個網際網路公開。允許假素材與模型清單，
不得包含座標、通行憑證、真實索引或素材原檔。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_PRIVATE_KEYS = {
    "gps",
    "lat",
    "lon",
    "latitude",
    "longitude",
    "gpslatitude",
    "gpslongitude",
}
_ALLOWED_SUFFIXES = {".html", ".css", ".js", ".json", ".webmanifest", ".png", ".md", ".svg", ".txt"}
_ALLOWED_PNG = {
    Path("icons/apple-touch-icon.png"),
    Path("icons/icon-192.png"),
    Path("icons/icon-512.png"),
}
_MAX_BYTES = 1_500_000


class PreviewPublishError(RuntimeError):
    pass


def assert_public_preview(root: Path) -> None:
    if not (root / "index.html").is_file():
        raise PreviewPublishError(f"找不到預覽頁：{root / 'index.html'}")
    snapshot = root / "preview" / "snapshot.json"
    if not snapshot.is_file():
        raise PreviewPublishError(f"找不到預覽資料：{snapshot}")
    errors: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            errors.append(f"不公開符號連結：{path.relative_to(root)}")
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.name in {"monitor.token", ".env", "settings.yaml"} or "library.json" in path.name:
            errors.append(f"不公開這個檔案：{relative}")
            continue
        suffix = path.suffix.lower()
        if suffix not in _ALLOWED_SUFFIXES:
            errors.append(f"這個類型不能放上公開頁：{relative}")
            continue
        if suffix == ".png" and relative not in _ALLOWED_PNG:
            errors.append(f"只允許內建圖示，不能放其他圖片：{relative}")
        if path.stat().st_size > _MAX_BYTES:
            errors.append(f"檔案過大，不像預覽頁資源：{relative}")
        if suffix == ".json":
            _check_json(path, relative, errors)
    if errors:
        raise PreviewPublishError("\n".join(errors))


def enable_public_pages() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("沒有 GitHub 權杖，略過 Pages 設定，改由部署步驟建立網站。")
        return
    status, payload = _request(token, repo, "POST", {"build_type": "workflow", "public": True})
    if status in {409, 422}:
        status, payload = _request(token, repo, "PUT", {"build_type": "workflow", "public": True})
    if status in {200, 201, 204} and isinstance(payload, dict) and payload.get("public") is True:
        print(f"已把 Pages 設成公開：{payload.get('html_url', '')}")
        return
    print(f"無法用 API 預先建立 Pages（HTTP {status}）。將改由 GitHub Actions 部署。")
    if payload:
        print(json.dumps(payload, ensure_ascii=False)[:800])


def _check_json(path: Path, relative: Path, errors: list[str]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"JSON 無法讀取：{relative}")
        return
    _reject_keys(payload, relative, errors)
    if path.name != "snapshot.json":
        return
    if not isinstance(payload, dict) or payload.get("preview") is not True:
        errors.append("預覽資料沒有標成 preview。")
        return
    for asset in payload.get("assets") or []:
        asset_id = str(asset.get("id", ""))
        asset_path = str(asset.get("relative_path", ""))
        if not asset_id.startswith("preview-") or not asset_path.startswith("preview/"):
            errors.append(f"預覽頁出現非預覽素材：{asset_id or asset_path}")


def _reject_keys(value: object, relative: Path, errors: list[str]) -> None:
    if isinstance(value, dict):
        found = _PRIVATE_KEYS.intersection(key.lower() for key in value)
        if found:
            errors.append(f"{relative} 含有座標欄位：{', '.join(sorted(found))}")
        for item in value.values():
            _reject_keys(item, relative, errors)
    elif isinstance(value, list):
        for item in value:
            _reject_keys(item, relative, errors)


def _request(token: str, repo: str, method: str, payload: dict | None) -> tuple[int, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pages",
        data=data,
        method=method,
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"message": body[:500]}
        return exc.code, parsed


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "web")
    try:
        assert_public_preview(root)
    except PreviewPublishError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    print(f"公開頁只含預覽資料：{root}")
    enable_public_pages()


if __name__ == "__main__":
    main()
