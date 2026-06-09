#!/usr/bin/env python3
"""Apply sql/017_content_reports.sql and moderation indexes idempotently."""

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


def index_exists(cur: pymysql.cursors.Cursor, table: str, name: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (settings.db_name, table, name),
    )
    return cur.fetchone()[0] > 0


def main() -> None:
    settings = get_settings()
    sql_path = ROOT / "sql" / "017_content_reports.sql"
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        ssl=build_ssl(),
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            for stmt in sql_path.read_text(encoding="utf-8").split(";"):
                clean = stmt.strip()
                if clean and not clean.startswith("--"):
                    cur.execute(clean)

            indexes = [
                (
                    "idx_content_reports_entity",
                    "ALTER TABLE content_reports ADD INDEX idx_content_reports_entity (entity_type_id, entity_id)",
                ),
                (
                    "idx_content_reports_reporter_entity",
                    "ALTER TABLE content_reports ADD INDEX idx_content_reports_reporter_entity (reporter_user_id, entity_type_id, entity_id)",
                ),
                (
                    "idx_content_reports_open_queue",
                    "ALTER TABLE content_reports ADD INDEX idx_content_reports_open_queue (status_id, entity_type_id, created_at DESC)",
                ),
            ]
            for name, ddl in indexes:
                if index_exists(cur, "content_reports", name):
                    print(f"  Index {name} exists — skipped")
                else:
                    cur.execute(ddl)
                    print(f"  Added index {name}")
        conn.commit()
        print("Applied content reports migration (017)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
