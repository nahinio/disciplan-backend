#!/usr/bin/env python3
"""Apply seed + views only (idempotent-ish)."""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


def run_file(conn: pymysql.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    statements = []
    for raw in sql.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        # Strip leading SQL comment lines so view DDL isn't skipped
        lines = [ln for ln in stmt.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    with conn.cursor() as cur:
        for i, stmt in enumerate(statements, 1):
            try:
                cur.execute(stmt)
            except Exception as exc:
                preview = " ".join(stmt.split())[:80]
                raise RuntimeError(f"Failed statement {i} in {path.name}: {preview}... -> {exc}") from exc
    conn.commit()
    print(f"  Applied {path.name} ({len(statements)} statements)")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Apply seed SQL files")
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Run specific files only (e.g. 004_seed_academic.sql)",
    )
    args = parser.parse_args()

    settings = get_settings()
    ctx = ssl.create_default_context(cafile=str(ROOT / "certs" / "ca.pem"))
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        ssl=ctx,
        autocommit=False,
    )
    try:
        names = args.only or ("002_seed.sql", "003_views.sql")
        for name in names:
            run_file(conn, ROOT / "sql" / name)
        print("Seed and views applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
