#!/usr/bin/env python3
"""Apply sql/024_doubt_accept.sql idempotently."""

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


def column_exists(cur: pymysql.cursors.Cursor, table: str, column: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (settings.db_name, table, column),
    )
    return cur.fetchone()[0] > 0


def fk_exists(cur: pymysql.cursors.Cursor, table: str, constraint: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (settings.db_name, table, constraint),
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
            if not column_exists(cur, "section_doubts", "accepted_answer_id"):
                cur.execute(
                    "ALTER TABLE section_doubts "
                    "ADD COLUMN accepted_answer_id BIGINT UNSIGNED NULL AFTER is_verified"
                )
                print("Added section_doubts.accepted_answer_id")
            else:
                print("section_doubts.accepted_answer_id already exists")

            if not fk_exists(cur, "section_doubts", "fk_section_doubts_accepted_answer"):
                cur.execute(
                    """
                    ALTER TABLE section_doubts
                    ADD CONSTRAINT fk_section_doubts_accepted_answer
                        FOREIGN KEY (accepted_answer_id) REFERENCES section_doubt_answers (id)
                        ON DELETE SET NULL
                    """
                )
                print("Added fk_section_doubts_accepted_answer")
            else:
                print("fk_section_doubts_accepted_answer already exists")

            if not column_exists(cur, "section_doubt_answers", "is_faculty_endorsed"):
                cur.execute(
                    "ALTER TABLE section_doubt_answers "
                    "ADD COLUMN is_faculty_endorsed TINYINT(1) NOT NULL DEFAULT 0 "
                    "AFTER is_faculty_answer"
                )
                print("Added section_doubt_answers.is_faculty_endorsed")
            else:
                print("section_doubt_answers.is_faculty_endorsed already exists")

            cur.execute(
                """
                INSERT IGNORE INTO notification_types (code, label) VALUES
                    ('doubt_solution_accepted', 'Doubt solution accepted')
                """
            )

            cur.execute(
                """
                UPDATE section_doubt_answers a
                INNER JOIN section_doubts d ON d.id = a.doubt_id AND d.deleted_at IS NULL
                INNER JOIN users u ON u.id = a.author_user_id
                INNER JOIN roles r ON r.id = u.role_id
                SET a.is_faculty_endorsed = 1,
                    d.accepted_answer_id = COALESCE(d.accepted_answer_id, a.id)
                WHERE d.is_verified = 1
                  AND a.is_faculty_answer = 1
                  AND a.deleted_at IS NULL
                  AND r.code = 'student'
                """
            )
            print(f"Backfill endorsed answers: {cur.rowcount} rows")

            cur.execute(
                """
                UPDATE section_doubt_answers a
                INNER JOIN users u ON u.id = a.author_user_id
                INNER JOIN roles r ON r.id = u.role_id
                SET a.is_faculty_answer = 0
                WHERE a.is_faculty_endorsed = 1 AND r.code = 'student'
                """
            )
            print(f"Fixed is_faculty_answer on student rows: {cur.rowcount} rows")

        conn.commit()
        print("024_doubt_accept migration applied.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
