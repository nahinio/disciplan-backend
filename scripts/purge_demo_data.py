#!/usr/bin/env python3
"""Remove legacy demo courses, sections, and bootstrap test accounts from the database."""

from __future__ import annotations

import argparse
import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

DEMO_COURSE_CODES: tuple[str, ...] = (
    "CSE 1115",
    "CSE 1111",
    "CSE 1112",
    "CSE 3522",
)

DEMO_USER_EMAILS: tuple[str, ...] = (
    "faculty@disciplan.com",
    "admin@disciplan.com",
    "editor.admin@disciplan.com",
    "demo.faculty@uiu.ac.bd",
)


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
        ctx = ssl.create_default_context(cafile=str(ROOT / "certs" / "ca.pem"))
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        kwargs["ssl"] = ctx
    return pymysql.connect(**kwargs)


def purge_demo_courses(cur: pymysql.cursors.DictCursor) -> int:
    placeholders = ", ".join(["%s"] * len(DEMO_COURSE_CODES))
    cur.execute(
        f"SELECT id, code FROM courses WHERE code IN ({placeholders})",
        DEMO_COURSE_CODES,
    )
    rows = cur.fetchall()
    if not rows:
        print("No demo courses found.")
        return 0

    course_ids = [row["id"] for row in rows]
    id_placeholders = ", ".join(["%s"] * len(course_ids))

    cur.execute(
        f"SELECT id FROM sections WHERE course_id IN ({id_placeholders})",
        course_ids,
    )
    section_ids = [row["id"] for row in cur.fetchall()]

    if section_ids:
        sec_ph = ", ".join(["%s"] * len(section_ids))
        cur.execute(f"DELETE FROM section_meeting_times WHERE section_id IN ({sec_ph})", section_ids)
        cur.execute(f"DELETE FROM section_faculty WHERE section_id IN ({sec_ph})", section_ids)
        cur.execute(f"DELETE FROM section_enrollments WHERE section_id IN ({sec_ph})", section_ids)
        cur.execute(f"DELETE FROM sections WHERE id IN ({sec_ph})", section_ids)
        print(f"Removed {len(section_ids)} demo section(s).")

    cur.execute(f"DELETE FROM syllabus_topics WHERE course_id IN ({id_placeholders})", course_ids)
    cur.execute(f"DELETE FROM course_user_preferences WHERE course_id IN ({id_placeholders})", course_ids)
    cur.execute(f"DELETE FROM courses WHERE id IN ({id_placeholders})", course_ids)
    print(f"Removed {len(course_ids)} demo course(s): {', '.join(row['code'] for row in rows)}")
    return len(course_ids)


def purge_demo_users(cur: pymysql.cursors.DictCursor) -> int:
    removed = 0
    for email in DEMO_USER_EMAILS:
        cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
        row = cur.fetchone()
        if not row:
            continue
        user_id = row["id"]
        cur.execute(
            "DELETE FROM faculty_roster WHERE LOWER(email) = LOWER(%s) OR claimed_user_id = %s",
            (email, user_id),
        )
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        print(f"Removed demo user: {email} (id={user_id})")
        removed += 1
    if removed == 0:
        print("No demo users found.")
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge legacy DisciPlan demo seed data")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required — actually delete demo rows",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("This will delete demo courses and bootstrap test accounts.")
        print("Re-run with --confirm to apply.")
        print(f"  Courses: {', '.join(DEMO_COURSE_CODES)}")
        print(f"  Users:   {', '.join(DEMO_USER_EMAILS)}")
        sys.exit(0)

    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            courses = purge_demo_courses(cur)
            users = purge_demo_users(cur)
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print(f"Done. Removed {courses} course(s) and {users} user(s).")
    except Exception as exc:
        conn.rollback()
        raise SystemExit(f"Purge failed: {exc}") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
