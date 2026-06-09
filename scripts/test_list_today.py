#!/usr/bin/env python3
import asyncio
import ssl
import sys
import time
from datetime import date
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.services import task_planner_service  # noqa: E402


def get_student_id() -> int:
    settings = get_settings()
    ca = Path(settings.db_ssl_ca_path)
    ctx = ssl.create_default_context(cafile=str(ca)) if ca.exists() else ssl.create_default_context()
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        ssl=ctx,
        connect_timeout=15,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", ("phase2user@uiu.ac.bd",))
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


async def main() -> None:
    uid = get_student_id()
    print(f"student_id={uid}")
    t0 = time.time()
    items = await task_planner_service.list_today(uid, "student", target_date=date.today())
    print(f"tasks={len(items)} elapsed={time.time() - t0:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
