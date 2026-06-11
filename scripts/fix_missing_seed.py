#!/usr/bin/env python3
"""Ensure core lookup rows exist (roles, departments). No demo courses."""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    ca_path = ROOT / "certs" / "ca.pem"
    if ca_path.exists():
        ctx = ssl.create_default_context(cafile=str(ca_path))
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        ssl=ctx,
    )
    cur = conn.cursor()
    cur.execute(
        "INSERT IGNORE INTO roles (code, label) VALUES "
        "('student','Student'),('faculty','Faculty'),('admin','Administrator')"
    )
    cur.execute(
        "INSERT IGNORE INTO departments (code, name) VALUES "
        "('CSE', 'Computer Science & Engineering'),"
        "('BBA', 'Business Administration'),"
        "('EEE', 'Electrical & Electronic Engineering')"
    )
    conn.commit()
    for table in ("roles", "departments"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {cur.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
