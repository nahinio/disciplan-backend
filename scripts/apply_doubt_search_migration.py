#!/usr/bin/env python3
"""Apply sql/023_doubt_search.sql idempotently."""

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


def index_exists(cur: pymysql.cursors.Cursor, table: str, index_name: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (settings.db_name, table, index_name),
    )
    return cur.fetchone()[0] > 0


def main() -> None:
    settings = get_settings()
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        ssl=build_ssl(),
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            if not index_exists(cur, "section_doubts", "ft_section_doubts_title_body"):
                cur.execute(
                    "ALTER TABLE section_doubts "
                    "ADD FULLTEXT INDEX ft_section_doubts_title_body (title, body)"
                )
                print("Added ft_section_doubts_title_body")
            else:
                print("ft_section_doubts_title_body already exists")

            if not index_exists(cur, "section_doubt_answers", "ft_doubt_answers_body"):
                cur.execute(
                    "ALTER TABLE section_doubt_answers "
                    "ADD FULLTEXT INDEX ft_doubt_answers_body (body)"
                )
                print("Added ft_doubt_answers_body")
            else:
                print("ft_doubt_answers_body already exists")
        conn.commit()
        print("023_doubt_search migration applied.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
