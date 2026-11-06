#!/usr/bin/env python3
"""只在 GitHub Pages 能限制成倉庫成員時才允許發佈。

個人帳號的私人倉庫一旦開啟 Pages，網站仍會對整個網際網路公開。
這個腳本先要求 public 為 false；做不到就不要發佈，並刪掉誤建的公開站。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def site_is_private(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("public") is False


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        skip("缺少發佈用的 GitHub 權杖或倉庫名稱，沒有發佈。")
        return
    status, payload = request(token, repo, "POST", {"build_type": "workflow", "public": False})
    created = status in {200, 201}
    if status in {409, 422}:
        status, payload = request(
            token,
            repo,
            "PUT",
            {"build_type": "workflow", "public": False},
        )
    if site_is_private(payload):
        url = payload.get("html_url") or ""
        print(f"Pages 只對倉庫讀取權限開放：{url}")
        set_output("deploy", "true")
        set_output("url", str(url))
        write_summary(f"將發佈只有倉庫成員能開啟的監控頁：{url}")
        return
    if created or (isinstance(payload, dict) and payload.get("public") is True):
        delete_status, delete_payload = request(token, repo, "DELETE", None)
        if delete_status not in {200, 202, 204, 404}:
            fail("偵測到公開的 GitHub Pages，而且無法刪除。請到倉庫的 Pages 設定關掉它。", delete_payload)
    message = (
        "沒有發佈。這個帳號是個人帳號，私人倉庫的 GitHub Pages 仍會對整個網際網路公開。"
        "只有 GitHub Enterprise Cloud 的組織倉庫能把網站限制成有讀取權限的人。"
        "為了避免監控頁被外人打開，這次沒有上傳頁面。"
    )
    skip(message, payload)


def request(token: str, repo: str, method: str, payload: dict | None) -> tuple[int, object]:
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


def skip(message: str, payload: object | None = None) -> None:
    print(message)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False)[:1000])
    print(f"::warning title=未發佈監控頁::{message}")
    set_output("deploy", "false")
    write_summary(message)


def fail(message: str, payload: object) -> None:
    print(message)
    print(json.dumps(payload, ensure_ascii=False)[:1000])
    write_summary(message)
    sys.exit(1)


def set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def write_summary(message: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(message + "\n")


if __name__ == "__main__":
    main()
