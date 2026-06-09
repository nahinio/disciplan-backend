#!/usr/bin/env python3
"""Apply sql/018_blog_post_tags.sql idempotently."""

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


def table_exists(conn: pymysql.Connection, table: str) -> bool:
    settings = get_settings()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (settings.db_name, table),
        )
        row = cur.fetchone()
    return bool(row and row[0] > 0)


def main() -> None:
    settings = get_settings()
    sql_path = ROOT / "sql" / "018_blog_post_tags.sql"
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
        if table_exists(conn, "blog_tags") and table_exists(conn, "blog_post_tags"):
            print("  blog_tags and blog_post_tags already exist — skipped")
        else:
            print("  Applying 018_blog_post_tags.sql ...")
            script = sql_path.read_text(encoding="utf-8")
            statements = [s.strip() for s in script.split(";") if s.strip()]
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            conn.commit()
        print("Blog tags migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
