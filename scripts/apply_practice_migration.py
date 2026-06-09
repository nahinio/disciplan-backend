#!/usr/bin/env python3
"""Apply sql/009_practice_problem_media.sql idempotently."""

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
              AND TABLE_NAME = 'practice_problems'
              AND COLUMN_NAME = %s
            """,
            (settings.db_name, column),
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
            if not column_exists(conn, "problem_number"):
                print("  Adding problem_number ...")
                cur.execute(
                    """
                    ALTER TABLE practice_problems
                        ADD COLUMN problem_number SMALLINT UNSIGNED NULL AFTER topic_id
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE practice_problems
                        ADD KEY idx_practice_problems_topic_number (topic_id, problem_number)
                    """
                )
            else:
                print("  problem_number already exists — skipped")

            if not column_exists(conn, "question_image_file_id"):
                print("  Adding question_image_file_id ...")
                cur.execute(
                    """
                    ALTER TABLE practice_problems
                        ADD COLUMN question_image_file_id BIGINT UNSIGNED NULL AFTER answer_text
                    """
                )
            else:
                print("  question_image_file_id already exists — skipped")

            if not column_exists(conn, "answer_image_file_id"):
                print("  Adding answer_image_file_id ...")
                cur.execute(
                    """
                    ALTER TABLE practice_problems
                        ADD COLUMN answer_image_file_id BIGINT UNSIGNED NULL
                        AFTER question_image_file_id
                    """
                )
            else:
                print("  answer_image_file_id already exists — skipped")

            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE CONSTRAINT_SCHEMA = %s
                  AND TABLE_NAME = 'practice_problems'
                  AND CONSTRAINT_NAME = 'fk_practice_problems_question_image'
                """,
                (settings.db_name,),
            )
            if cur.fetchone()[0] == 0:
                print("  Adding image foreign keys ...")
                cur.execute(
                    """
                    ALTER TABLE practice_problems
                        ADD CONSTRAINT fk_practice_problems_question_image
                            FOREIGN KEY (question_image_file_id) REFERENCES files (id)
                            ON DELETE SET NULL,
                        ADD CONSTRAINT fk_practice_problems_answer_image
                            FOREIGN KEY (answer_image_file_id) REFERENCES files (id)
                            ON DELETE SET NULL
                    """
                )
            else:
                print("  image foreign keys already exist — skipped")

        conn.commit()
        print("Practice migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
