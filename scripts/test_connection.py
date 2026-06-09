#!/usr/bin/env python3
"""Verify Aiven MySQL connectivity."""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    ca = Path(settings.db_ssl_ca_path)
    ctx = None
    if settings.db_ssl:
        ctx = ssl.create_default_context(cafile=str(ca)) if ca.exists() else ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

    print(f"Host: {settings.db_host}:{settings.db_port}")
    print(f"User: {settings.db_user}")
    print(f"Database: {settings.db_name}")
    print(f"SSL CA: {ca} ({'found' if ca.exists() else 'MISSING'})")

    try:
        conn = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            ssl=ctx,
            connect_timeout=15,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS version, DATABASE() AS db")
            row = cur.fetchone()
        conn.close()
        print(f"SUCCESS — MySQL {row[0]}, database={row[1]}")
    except pymysql.err.OperationalError as exc:
        print(f"FAILED — {exc}")
        if exc.args[0] == 1045:
            print()
            print("Fix in Aiven Console:")
            print("  1. Service > Connection information > Reset password > update .env")
            print("  2. Service settings > IP allowlist > ensure 0.0.0.0/0 (or add your IP)")
            print("  3. Service settings > ensure Public access is enabled for MySQL")
        sys.exit(1)


if __name__ == "__main__":
    main()
