#!/usr/bin/env python3
"""Apply sql/015_planner_tasks.sql idempotently."""

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


def table_exists(cur: pymysql.cursors.Cursor, table: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (settings.db_name, table),
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
            if not table_exists(cur, "planner_task_types"):
                cur.execute(
                    """
                    CREATE TABLE planner_task_types (
                        id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
                        code VARCHAR(40) NOT NULL,
                        label VARCHAR(80) NOT NULL,
                        role_scope ENUM('student','faculty','both') NOT NULL,
                        sort_order TINYINT UNSIGNED NOT NULL DEFAULT 0,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_planner_task_types_code (code)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                print("  Created planner_task_types")
                seeds = [
                    ("lecture", "Lecture", "both", 1),
                    ("grading", "Grading", "faculty", 2),
                    ("exam_quiz", "Exam / Quiz", "faculty", 3),
                    ("meeting", "Meeting", "faculty", 4),
                    ("personal", "Personal", "faculty", 5),
                    ("ct", "CT", "student", 2),
                    ("assignment", "Assignment", "student", 3),
                    ("presentation", "Presentation", "student", 4),
                    ("personal_goal", "Personal goal", "student", 5),
                ]
                for code, label, scope, order in seeds:
                    cur.execute(
                        """
                        INSERT IGNORE INTO planner_task_types (code, label, role_scope, sort_order)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (code, label, scope, order),
                    )
            else:
                print("  planner_task_types already exists — skipped")

            alters = [
                ("planner_task_type_id", "TINYINT UNSIGNED NULL AFTER assessment_type_id"),
                ("section_id", "INT UNSIGNED NULL AFTER course_id"),
                ("completion_percent", "TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER is_completed"),
                ("estimated_effort_min", "SMALLINT UNSIGNED NULL AFTER energy_level_id"),
                ("computed_weight", "DECIMAL(12,4) NOT NULL DEFAULT 0 AFTER estimated_effort_min"),
                ("is_skipped", "TINYINT(1) NOT NULL DEFAULT 0 AFTER computed_weight"),
                ("skipped_at", "DATETIME(3) NULL AFTER is_skipped"),
                ("original_due_at", "DATETIME(3) NULL AFTER due_at"),
                ("reschedule_count", "SMALLINT UNSIGNED NOT NULL DEFAULT 0 AFTER skipped_at"),
                ("source", "VARCHAR(20) NOT NULL DEFAULT 'manual' AFTER reschedule_count"),
                ("attachment_file_id", "BIGINT UNSIGNED NULL AFTER description"),
                ("calendar_event_id", "BIGINT UNSIGNED NULL AFTER attachment_file_id"),
                ("scheduled_for_date", "DATE NULL AFTER calendar_event_id"),
            ]
            for col, definition in alters:
                if not column_exists(cur, "user_tasks", col):
                    cur.execute(f"ALTER TABLE user_tasks ADD COLUMN {col} {definition}")
                    print(f"  Added user_tasks.{col}")

            if not table_exists(cur, "user_daily_energy"):
                cur.execute(
                    """
                    CREATE TABLE user_daily_energy (
                        user_id BIGINT UNSIGNED NOT NULL,
                        energy_date DATE NOT NULL,
                        energy_level_id TINYINT UNSIGNED NOT NULL,
                        set_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                        PRIMARY KEY (user_id, energy_date),
                        CONSTRAINT fk_user_daily_energy_user
                            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                        CONSTRAINT fk_user_daily_energy_level
                            FOREIGN KEY (energy_level_id) REFERENCES energy_levels (id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                print("  Created user_daily_energy")
            else:
                print("  user_daily_energy already exists — skipped")

            if not table_exists(cur, "user_lecture_task_log"):
                cur.execute(
                    """
                    CREATE TABLE user_lecture_task_log (
                        user_id BIGINT UNSIGNED NOT NULL,
                        section_id INT UNSIGNED NOT NULL,
                        meeting_time_id INT UNSIGNED NOT NULL,
                        lecture_date DATE NOT NULL,
                        task_id BIGINT UNSIGNED NOT NULL,
                        PRIMARY KEY (user_id, meeting_time_id, lecture_date),
                        KEY idx_lecture_log_task (task_id),
                        CONSTRAINT fk_lecture_log_user
                            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                        CONSTRAINT fk_lecture_log_section
                            FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
                        CONSTRAINT fk_lecture_log_meeting
                            FOREIGN KEY (meeting_time_id) REFERENCES section_meeting_times (id) ON DELETE CASCADE,
                        CONSTRAINT fk_lecture_log_task
                            FOREIGN KEY (task_id) REFERENCES user_tasks (id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                print("  Created user_lecture_task_log")
            else:
                print("  user_lecture_task_log already exists — skipped")

        conn.commit()
        print("Planner tasks migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
