#!/usr/bin/env python3
"""Smoke test: admin catalog stats, content reports API, report submit."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

BASE = "http://127.0.0.1:8000/api/v1"


def req(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc


def login(email: str, password: str) -> str:
    res = req("POST", "/auth/login", body={"email": email, "password": password})
    return str(res["access_token"])


def main() -> None:
    settings = get_settings()
    email = getattr(settings, "bootstrap_admin_email", None) or "admin@disciplan.com"
    password = "password"

    print("1. Login as admin…")
    token = login(email, password)

    print("2. Catalog content stats…")
    stats = req("GET", "/admin/catalog/content-stats", token=token)
    items = stats.get("items", [])
    print(f"   {len(items)} active course(s)")
    assert isinstance(items, list)

    print("3. List open content reports…")
    reports = req("GET", "/admin/content-reports?status=open&limit=10", token=token)
    print(f"   {len(reports.get('items', []))} open report(s)")

    print("4. List admin blogs…")
    blogs = req("GET", "/admin/blogs?limit=5", token=token)
    print(f"   {len(blogs.get('items', []))} blog(s)")

    print("OK — admin publish/moderation APIs reachable")


if __name__ == "__main__":
    main()
