#!/usr/bin/env python3
"""Migrate section_grade_components.component_type enum to include final and assignment."""

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
    # Bypass verification for quick migration run
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
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
            # Check current column details
            cur.execute(
                """
                SELECT COLUMN_TYPE FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'section_grade_components'
                  AND COLUMN_NAME = 'component_type'
                """,
                (settings.db_name,),
            )
            row = cur.fetchone()
            if row:
                print(f"Current column type: {row[0]}")
            
            print("Altering section_grade_components.component_type ENUM...")
            cur.execute(
                """
                ALTER TABLE section_grade_components
                MODIFY COLUMN component_type ENUM('ct', 'evaluation', 'attendance', 'portal', 'team', 'final', 'assignment') NOT NULL
                """
            )
            print("Successfully migrated column type!")
        conn.commit()
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
