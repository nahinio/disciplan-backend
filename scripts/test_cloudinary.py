#!/usr/bin/env python3
"""Verify Cloudinary credentials (requires CLOUDINARY_CLOUD_NAME in .env)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.utils.cloudinary import configure_cloudinary  # noqa: E402

import cloudinary.api  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.cloudinary_cloud_name:
        print("CLOUDINARY_CLOUD_NAME is empty in .env")
        print("Find it in Cloudinary Dashboard → Product environment credentials → Cloud name")
        sys.exit(1)

    configure_cloudinary()
    try:
        result = cloudinary.api.ping()
        print(f"SUCCESS — Cloudinary ping OK for cloud '{settings.cloudinary_cloud_name}'")
        print(result)
    except Exception as exc:
        print(f"FAILED — {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
