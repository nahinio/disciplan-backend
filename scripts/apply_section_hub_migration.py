#!/usr/bin/env python3
"""Apply sql/016_section_hub.sql idempotently."""

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


def constraint_exists(cur: pymysql.cursors.Cursor, table: str, name: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (settings.db_name, table, name),
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
            if not table_exists(cur, "section_resources"):
                cur.execute(
                    """
                    CREATE TABLE section_resources (
                        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                        section_id INT UNSIGNED NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        description TEXT NULL,
                        resource_kind ENUM('file', 'link') NOT NULL DEFAULT 'file',
                        file_id BIGINT UNSIGNED NULL,
                        external_url VARCHAR(500) NULL,
                        mime_category ENUM('pdf', 'pptx', 'image', 'doc', 'other') NOT NULL DEFAULT 'other',
                        sort_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                        created_by_user_id BIGINT UNSIGNED NOT NULL,
                        created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                        deleted_at DATETIME(3) NULL,
                        PRIMARY KEY (id),
                        KEY idx_section_resources_section (section_id, sort_order, created_at DESC),
                        CONSTRAINT fk_section_resources_section
                            FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
                        CONSTRAINT fk_section_resources_file
                            FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE SET NULL,
                        CONSTRAINT fk_section_resources_creator
                            FOREIGN KEY (created_by_user_id) REFERENCES users (id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                print("  Created section_resources")
            else:
                print("  section_resources already exists — skipped")

            for table, col, definition in [
                ("practice_problems", "section_id", "INT UNSIGNED NULL AFTER course_id"),
                ("past_papers", "section_id", "INT UNSIGNED NULL AFTER course_id"),
            ]:
                if not column_exists(cur, table, col):
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
                    print(f"  Added {table}.{col}")

            comment_cols = [
                ("parent_comment_id", "BIGINT UNSIGNED NULL AFTER announcement_id"),
                ("is_pinned", "TINYINT(1) NOT NULL DEFAULT 0 AFTER body"),
                ("pinned_by_user_id", "BIGINT UNSIGNED NULL AFTER is_pinned"),
                ("pinned_at", "DATETIME(3) NULL AFTER pinned_by_user_id"),
            ]
            for col, definition in comment_cols:
                if not column_exists(cur, "section_announcement_comments", col):
                    cur.execute(
                        f"ALTER TABLE section_announcement_comments ADD COLUMN {col} {definition}"
                    )
                    print(f"  Added section_announcement_comments.{col}")

            if not table_exists(cur, "section_grade_components"):
                cur.execute(
                    """
                    CREATE TABLE section_grade_components (
                        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                        section_id INT UNSIGNED NOT NULL,
                        component_type ENUM('ct', 'evaluation', 'attendance', 'portal', 'team') NOT NULL,
                        label VARCHAR(80) NOT NULL,
                        component_code VARCHAR(40) NOT NULL,
                        max_score DECIMAL(6,2) NOT NULL DEFAULT 100.00,
                        weight_percent DECIMAL(5,2) NOT NULL DEFAULT 0,
                        portal_id BIGINT UNSIGNED NULL,
                        team_id BIGINT UNSIGNED NULL,
                        sort_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                        is_active TINYINT(1) NOT NULL DEFAULT 1,
                        created_by_user_id BIGINT UNSIGNED NOT NULL,
                        created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_section_grade_components_code (section_id, component_code),
                        KEY idx_section_grade_components_section (section_id, sort_order),
                        CONSTRAINT fk_section_grade_components_section
                            FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
                        CONSTRAINT fk_section_grade_components_portal
                            FOREIGN KEY (portal_id) REFERENCES assessment_portals (id) ON DELETE SET NULL,
                        CONSTRAINT fk_section_grade_components_team
                            FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE SET NULL,
                        CONSTRAINT fk_section_grade_components_creator
                            FOREIGN KEY (created_by_user_id) REFERENCES users (id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                print("  Created section_grade_components")
            else:
                print("  section_grade_components already exists — skipped")

            if not column_exists(cur, "section_grades", "feedback"):
                cur.execute("ALTER TABLE section_grades ADD COLUMN feedback TEXT NULL AFTER max_score")
                print("  Added section_grades.feedback")

            if not table_exists(cur, "grade_scales"):
                cur.execute(
                    """
                    CREATE TABLE grade_scales (
                        id TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
                        min_percent DECIMAL(5,2) NOT NULL,
                        max_percent DECIMAL(5,2) NOT NULL,
                        letter_grade VARCHAR(5) NOT NULL,
                        gpa_points DECIMAL(3,2) NOT NULL,
                        sort_order TINYINT UNSIGNED NOT NULL DEFAULT 0,
                        PRIMARY KEY (id),
                        KEY idx_grade_scales_range (min_percent, max_percent)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                scales = [
                    (93, 100, "A+", 4.00, 1),
                    (90, 92.99, "A", 4.00, 2),
                    (87, 89.99, "A-", 3.70, 3),
                    (83, 86.99, "B+", 3.30, 4),
                    (80, 82.99, "B", 3.00, 5),
                    (77, 79.99, "B-", 2.70, 6),
                    (73, 76.99, "C+", 2.30, 7),
                    (70, 72.99, "C", 2.00, 8),
                    (67, 69.99, "C-", 1.70, 9),
                    (60, 66.99, "D", 1.00, 10),
                    (0, 59.99, "F", 0.00, 11),
                ]
                for row in scales:
                    cur.execute(
                        """
                        INSERT IGNORE INTO grade_scales
                            (min_percent, max_percent, letter_grade, gpa_points, sort_order)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        row,
                    )
                print("  Created grade_scales + seeds")
            else:
                print("  grade_scales already exists — skipped")

            if not table_exists(cur, "student_semester_summaries"):
                cur.execute(
                    """
                    CREATE TABLE student_semester_summaries (
                        user_id BIGINT UNSIGNED NOT NULL,
                        semester_id SMALLINT UNSIGNED NOT NULL,
                        total_credits DECIMAL(5,1) NOT NULL DEFAULT 0,
                        quality_points DECIMAL(8,2) NOT NULL DEFAULT 0,
                        cgpa DECIMAL(4,2) NOT NULL DEFAULT 0,
                        updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                            ON UPDATE CURRENT_TIMESTAMP(3),
                        PRIMARY KEY (user_id, semester_id),
                        CONSTRAINT fk_semester_summaries_user
                            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                        CONSTRAINT fk_semester_summaries_semester
                            FOREIGN KEY (semester_id) REFERENCES semesters (id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
                print("  Created student_semester_summaries")
            else:
                print("  student_semester_summaries already exists — skipped")

            if not column_exists(cur, "teams", "leader_user_id"):
                cur.execute(
                    "ALTER TABLE teams ADD COLUMN leader_user_id BIGINT UNSIGNED NULL "
                    "AFTER created_by_user_id"
                )
                print("  Added teams.leader_user_id")

            if not column_exists(cur, "chat_groups", "team_id"):
                cur.execute(
                    "ALTER TABLE chat_groups ADD COLUMN team_id BIGINT UNSIGNED NULL AFTER section_id"
                )
                print("  Added chat_groups.team_id")

        conn.commit()
        print("Section hub migration applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
