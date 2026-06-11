#!/usr/bin/env python3
"""Create the first admin account from environment variables."""

from __future__ import annotations

import os
import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.utils.security import hash_password


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


def upsert_admin(
    cur: pymysql.cursors.DictCursor,
    email: str,
    password: str,
    name: str,
    role_id: int,
    status_id: int,
) -> None:
    cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
    existing = cur.fetchone()
    pwd_hash = hash_password(password)

    if existing:
        cur.execute(
            """
            UPDATE users
            SET password_hash = %s, role_id = %s, status_id = %s, email_verified = 1
            WHERE id = %s
            """,
            (pwd_hash, role_id, status_id, existing["id"]),
        )
        user_id = existing["id"]
        cur.execute(
            """
            INSERT INTO user_profiles (user_id, display_name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE display_name = VALUES(display_name)
            """,
            (user_id, name),
        )
        print(f"Reset admin: {email} (id={user_id})")
    else:
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
        print(f"Created admin: {email} (id={user_id})")


def main() -> None:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "Administrator").strip()

    if not email or not password:
        print(
            "Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD in the environment.\n"
            "Optional: BOOTSTRAP_ADMIN_NAME (default: Administrator)"
        )
        sys.exit(1)

    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM roles WHERE code = 'admin' LIMIT 1")
            role = cur.fetchone()
            if not role:
                raise RuntimeError("Missing admin role — run migrations first.")

            cur.execute("SELECT id FROM user_statuses WHERE code = 'active' LIMIT 1")
            status = cur.fetchone()
            if not status:
                raise RuntimeError("Missing active user status.")

            upsert_admin(cur, email, password, name, role["id"], status["id"])

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
