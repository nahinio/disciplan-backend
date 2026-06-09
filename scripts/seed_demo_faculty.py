#!/usr/bin/env python3
"""Seed active demo faculty accounts for local/testing."""

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

DEFAULT_PASSWORD = os.environ.get("DEMO_FACULTY_PASSWORD", "TestPass123!").strip()

DEMO_FACULTY = [
    ("mahmudul.demo@uiu.ac.bd", "Mr. Mahmudul Hasan"),
    ("messi.demo@uiu.ac.bd", "Lionel Messi"),
    ("ronaldo.demo@uiu.ac.bd", "Christiano Ronaldo"),
    ("swiftie.demo@uiu.ac.bd", "Taylor Swift"),
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
        ctx = ssl.create_default_context(cafile=str(ROOT / "certs" / "ca.pem"))
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        kwargs["ssl"] = ctx
    return pymysql.connect(**kwargs)


def upsert_faculty(
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
        print(f"  Updated active faculty: {name} <{email}> (id={user_id})")
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
    print(f"  Created active faculty: {name} <{email}> (id={user_id})")
    return user_id


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

            print(f"Seeding {len(DEMO_FACULTY)} demo faculty (password: {DEFAULT_PASSWORD})")
            for email, name in DEMO_FACULTY:
                user_id = upsert_faculty(
                    cur, email, DEFAULT_PASSWORD, name, role["id"], status["id"]
                )
                cur.execute(
                    """
                    INSERT INTO faculty_roster (email, display_name, status, claimed_user_id, claimed_at)
                    VALUES (%s, %s, 'claimed', %s, UTC_TIMESTAMP(3))
                    ON DUPLICATE KEY UPDATE
                        display_name = VALUES(display_name),
                        status = 'claimed',
                        claimed_user_id = VALUES(claimed_user_id),
                        claimed_at = UTC_TIMESTAMP(3)
                    """,
                    (email.lower(), name, user_id),
                )

        conn.commit()
        print("\nDone. Demo faculty can log in with the shared password above.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
