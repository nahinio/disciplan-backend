#!/usr/bin/env python3
"""Apply sql/027_drop_course_user_preferences.sql idempotently."""

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
    return ssl._create_unverified_context()


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
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'course_user_preferences'
                """,
                (settings.db_name,),
            )
            if cur.fetchone()[0] > 0:
                cur.execute("DROP TABLE course_user_preferences")
                print("  Dropped course_user_preferences table")
            else:
                print("  course_user_preferences already absent — skipped")
        conn.commit()
        print("Course user preferences drop migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
