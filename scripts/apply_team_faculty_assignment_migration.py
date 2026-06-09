#!/usr/bin/env python3
"""Apply sql/014_team_faculty_assignment.sql idempotently."""

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


def column_exists(cur: pymysql.cursors.Cursor, column: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'teams' AND COLUMN_NAME = %s
        """,
        (settings.db_name, column),
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
        charset="utf8mb4",
        ssl=build_ssl(),
        connect_timeout=20,
    )
    try:
        with conn.cursor() as cur:
            if column_exists(cur, "assigned_by_faculty_user_id"):
                print("  assigned_by_faculty_user_id already exists — skipped DDL")
            else:
                cur.execute(
                    """
                    ALTER TABLE teams
                        ADD COLUMN assigned_by_faculty_user_id BIGINT UNSIGNED NULL AFTER leader_user_id
                    """
                )
                print("  Added assigned_by_faculty_user_id column")
                cur.execute(
                    """
                    ALTER TABLE teams
                        ADD CONSTRAINT fk_teams_faculty_assigner
                            FOREIGN KEY (assigned_by_faculty_user_id) REFERENCES users (id) ON DELETE SET NULL
                    """
                )
                print("  Added fk_teams_faculty_assigner")

            cur.execute(
                """
                UPDATE teams t
                INNER JOIN users u ON u.id = t.created_by_user_id
                INNER JOIN roles r ON r.id = u.role_id AND r.code IN ('faculty', 'admin')
                SET t.assigned_by_faculty_user_id = t.created_by_user_id
                WHERE t.assigned_by_faculty_user_id IS NULL
                """
            )
            print(f"  Backfilled faculty-assigned teams ({cur.rowcount} rows)")
        conn.commit()
        print("Team faculty assignment migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
