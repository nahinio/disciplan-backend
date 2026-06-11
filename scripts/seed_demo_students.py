#!/usr/bin/env python3
"""Seed active demo student accounts for local/testing."""

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

DEFAULT_PASSWORD = os.environ.get("DEMO_STUDENT_PASSWORD", "TestPass123!").strip()

DEMO_STUDENTS = [
    ("phase2user@uiu.ac.bd", "Dr. Mohammad Younus"),
    ("ssumaia2420448@bscse.uiu.ac.bd", "Sadia Akter Sumaia"),
    ("mparves2420507@bscse.uiu.ac.bd", "Masud Parves"),
    ("amite2420456@bscse.uiu.ac.bd", "Atika Hakim"),
    ("nnahin2420504@bscse.uiu.ac.bd", "Najib Hossain Nahin"),
]


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


def upsert_student(
    cur: pymysql.cursors.DictCursor,
    email: str,
    password: str,
    name: str,
    role_id: int,
    status_id: int,
) -> int:
    cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
    existing = cur.fetchone()
    pwd_hash = hash_password(password)

    if existing:
        user_id = existing["id"]
        cur.execute(
            """
            UPDATE users
            SET password_hash = %s, role_id = %s, status_id = %s, email_verified = 1
            WHERE id = %s
            """,
            (pwd_hash, role_id, status_id, user_id),
        )
        cur.execute(
            """
            INSERT INTO user_profiles (user_id, display_name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE display_name = VALUES(display_name)
            """,
            (user_id, name),
        )
        print(f"  Updated active student: {name} <{email}> (id={user_id})")
        return user_id

    cur.execute(
        """
        INSERT INTO users (email, password_hash, role_id, status_id, email_verified)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (email.lower(), pwd_hash, role_id, status_id),
    )
    user_id = cur.lastrowid
    cur.execute(
        "INSERT INTO user_profiles (user_id, display_name) VALUES (%s, %s)",
        (user_id, name),
    )
    cur.execute("INSERT IGNORE INTO user_preferences (user_id) VALUES (%s)", (user_id,))
    cur.execute(
        """
        INSERT IGNORE INTO user_gamification (user_id, tier_id, total_points)
        SELECT %s, gt.id, 0 FROM gamification_tiers gt WHERE gt.code = 'bronze' LIMIT 1
        """,
        (user_id,),
    )
    print(f"  Created active student: {name} <{email}> (id={user_id})")
    return user_id


def main() -> None:
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM roles WHERE code = 'student' LIMIT 1")
            role = cur.fetchone()
            cur.execute("SELECT id FROM user_statuses WHERE code = 'active' LIMIT 1")
            status = cur.fetchone()
            if not role or not status:
                raise RuntimeError("Missing student role or active status — run migrations first.")

            print(f"Seeding {len(DEMO_STUDENTS)} demo students (password: {DEFAULT_PASSWORD})")
            for email, name in DEMO_STUDENTS:
                upsert_student(cur, email, DEFAULT_PASSWORD, name, role["id"], status["id"])

        conn.commit()
        print("\nDone. Demo students can log in with the shared password above.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
