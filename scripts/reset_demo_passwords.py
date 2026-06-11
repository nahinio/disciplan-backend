#!/usr/bin/env python3
"""Reset passwords for all non-admin users to the shared demo password."""

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
        if settings.db_ssl_ca:
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_verify_locations(cadata=settings.db_ssl_ca)
        else:
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
    pwd_hash = hash_password(DEFAULT_PASSWORD)
    conn = connect()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.email, r.code AS role
                FROM users u
                INNER JOIN roles r ON r.id = u.role_id
                WHERE r.code <> 'admin'
                ORDER BY r.code, u.email
                """
            )
            users = cur.fetchall()
            if not users:
                print("No non-admin users found.")
                return

            cur.execute(
                """
                UPDATE users u
                INNER JOIN roles r ON r.id = u.role_id
                SET u.password_hash = %s
                WHERE r.code <> 'admin'
                """,
                (pwd_hash,),
            )

        conn.commit()
        print(f"Reset password for {len(users)} non-admin account(s) to: {DEFAULT_PASSWORD}\n")
        for row in users:
            print(f"  [{row['role']}] {row['email']} (id={row['id']})")
        print("\nAdmin account(s) were not changed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
