#!/usr/bin/env python3
"""Apply sql/011_user_avatar_preset.sql idempotently."""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


def build_ssl() -> ssl.SSLContext | None:
    settings = get_settings()
    if not settings.db_ssl:
        return None
    ca = Path(settings.db_ssl_ca_path)
    if ca.exists():
        ctx = ssl.create_default_context(cafile=str(ca))
    else:
        ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def main() -> None:
    settings = get_settings()
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        ssl=build_ssl(),
        connect_timeout=20,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'user_profiles'
                  AND COLUMN_NAME = 'avatar_preset'
                """,
                (settings.db_name,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    """
                    ALTER TABLE user_profiles
                        ADD COLUMN avatar_preset VARCHAR(40) NULL AFTER avatar_file_id
                    """
                )
                print("  Added avatar_preset column")
            else:
                print("  avatar_preset already exists — skipped")
        conn.commit()
        print("Avatar preset migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
