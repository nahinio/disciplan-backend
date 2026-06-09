#!/usr/bin/env python3
"""Generate lecture tasks for all active students/faculty (cron / Task Scheduler)."""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.lecture_task_service import generate_lecture_tasks_for_all_users  # noqa: E402


async def main() -> None:
    target = date.today() + timedelta(days=1)
    count = await generate_lecture_tasks_for_all_users(target_date=target)
    print(f"Generated {count} lecture tasks for {target.isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
