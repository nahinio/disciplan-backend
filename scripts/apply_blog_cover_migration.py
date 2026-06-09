#!/usr/bin/env python3
"""Apply sql/010_blog_cover_image.sql idempotently."""

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


def column_exists(conn: pymysql.Connection, column: str) -> bool:
    settings = get_settings()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'blog_posts'
              AND COLUMN_NAME = %s
            """,
            (settings.db_name, column),
        )
        row = cur.fetchone()
    return bool(row and row[0] > 0)


def constraint_exists(conn: pymysql.Connection, name: str) -> bool:
    settings = get_settings()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.TABLE_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = %s
              AND TABLE_NAME = 'blog_posts'
              AND CONSTRAINT_NAME = %s
            """,
            (settings.db_name, name),
        )
        row = cur.fetchone()
    return bool(row and row[0] > 0)


def main() -> None:
    settings = get_settings()
    print(f"Connecting to {settings.db_host}:{settings.db_port}/{settings.db_name} ...")
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
            if not column_exists(conn, "cover_image_file_id"):
                print("  Adding cover_image_file_id ...")
                cur.execute(
                    """
                    ALTER TABLE blog_posts
                        ADD COLUMN cover_image_file_id BIGINT UNSIGNED NULL AFTER body_html
                    """
                )
            else:
                print("  cover_image_file_id already exists — skipped")

            if not constraint_exists(conn, "fk_blog_posts_cover_image"):
                print("  Adding cover image foreign key ...")
                cur.execute(
                    """
                    ALTER TABLE blog_posts
                        ADD CONSTRAINT fk_blog_posts_cover_image
                            FOREIGN KEY (cover_image_file_id) REFERENCES files (id)
                            ON DELETE SET NULL
                    """
                )
            else:
                print("  fk_blog_posts_cover_image already exists — skipped")

        conn.commit()
        print("Blog cover migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
