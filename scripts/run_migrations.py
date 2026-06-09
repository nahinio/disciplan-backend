#!/usr/bin/env python3
"""Apply SQL migrations to Aiven MySQL (raw SQL, no ORM)."""

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
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def run_sql_file(conn: pymysql.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    statements = []
    for raw in sql.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        lines = [ln for ln in stmt.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    with conn.cursor() as cur:
        for stmt in statements:
            if stmt.upper().startswith("SET "):
                cur.execute(stmt)
                continue
            cur.execute(stmt)
    conn.commit()
    print(f"  Applied {path.name} ({len(statements)} statements)")


def main() -> None:
    settings = get_settings()
    sql_dir = ROOT / "sql"
    files = sorted(sql_dir.glob("*.sql"))

    if not files:
        print("No SQL files found.")
        return

    print(f"Connecting to {settings.db_host}:{settings.db_port}/{settings.db_name} ...")

    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        ssl=build_ssl(),
        autocommit=False,
    )
    try:
        for f in files:
            run_sql_file(conn, f)
        print("All migrations applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
