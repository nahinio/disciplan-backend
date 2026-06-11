#!/usr/bin/env python3
"""Create/update Phase 2 faculty test account and link to the first active section."""

from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

EMAIL = os.environ.get("BOOTSTRAP_FACULTY_EMAIL", "phase2faculty@uiu.ac.bd").strip().lower()
PASSWORD = os.environ.get("BOOTSTRAP_FACULTY_PASSWORD", "TestPass123!").strip()
NAME = os.environ.get("BOOTSTRAP_FACULTY_NAME", "Phase2 Faculty").strip()


def connect() -> pymysql.Connection:
    settings = get_settings()
    kwargs: dict = {
        "host": settings.db_host,
        "port": settings.db_port,
        "user": settings.db_user,
        "password": settings.db_password,
        "database": settings.db_name,
        "charset": "utf8mb4",
        "autocommit": False,
    }
    if settings.db_ssl:
        ca_path = ROOT / "certs" / "ca.pem"
        if ca_path.exists():
            ctx = ssl.create_default_context(cafile=str(ca_path))
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl"] = ctx
    return pymysql.connect(**kwargs)


def main() -> None:
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM roles WHERE code = 'faculty' LIMIT 1")
            role = cur.fetchone()
            cur.execute("SELECT id FROM user_statuses WHERE code = 'active' LIMIT 1")
            status = cur.fetchone()
            if not role or not status:
                raise RuntimeError("Missing faculty role or active status — run migrations first.")

            pwd_hash = hash_password(PASSWORD)
            cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (EMAIL,))
            existing = cur.fetchone()
            if existing:
                user_id = existing["id"]
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s, role_id = %s, status_id = %s, email_verified = 1
                    WHERE id = %s
                    """,
                    (pwd_hash, role["id"], status["id"], user_id),
                )
                cur.execute(
                    """
                    INSERT INTO user_profiles (user_id, display_name)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE display_name = VALUES(display_name)
                    """,
                    (user_id, NAME),
                )
                print(f"Reset faculty user: {EMAIL} (id={user_id})")
            else:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, role_id, status_id, email_verified)
                    VALUES (%s, %s, %s, %s, 1)
                    """,
                    (EMAIL, pwd_hash, role["id"], status["id"]),
                )
                user_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO user_profiles (user_id, display_name) VALUES (%s, %s)",
                    (user_id, NAME),
                )
                cur.execute("INSERT IGNORE INTO user_preferences (user_id) VALUES (%s)", (user_id,))
                print(f"Created faculty user: {EMAIL} (id={user_id})")

            cur.execute(
                """
                INSERT INTO faculty_roster (
                    email, display_name, status, claimed_user_id, claimed_at
                ) VALUES (%s, %s, 'claimed', %s, UTC_TIMESTAMP(3))
                ON DUPLICATE KEY UPDATE
                    display_name = VALUES(display_name),
                    status = 'claimed',
                    claimed_user_id = VALUES(claimed_user_id),
                    claimed_at = UTC_TIMESTAMP(3)
                """,
                (EMAIL, NAME, user_id),
            )

            cur.execute(
                """
                SELECT s.id, c.code AS course_code, s.section_label
                FROM sections s
                INNER JOIN courses c ON c.id = s.course_id
                INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
                WHERE s.is_active = 1
                ORDER BY c.code, s.section_label
                LIMIT 1
                """
            )
            section = cur.fetchone()
            if section:
                cur.execute(
                    """
                    INSERT IGNORE INTO section_faculty (section_id, faculty_user_id)
                    VALUES (%s, %s)
                    """,
                    (section["id"], user_id),
                )
                cur.execute(
                    """
                    SELECT id FROM chat_groups
                    WHERE section_id = %s AND is_active = 1
                    LIMIT 1
                    """,
                    (section["id"],),
                )
                group = cur.fetchone()
                if group:
                    cur.execute(
                        """
                        INSERT IGNORE INTO chat_group_members (group_id, user_id)
                        VALUES (%s, %s)
                        """,
                        (group["id"], user_id),
                    )
                print(
                    f"Assigned to section: {section['course_code']} :: {section['section_label']}"
                )
            else:
                print("No active sections found — assign teaching sections in Admin → Sections.")

        conn.commit()
        print(f"\nFaculty login:\n  Email:    {EMAIL}\n  Password: {PASSWORD}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
