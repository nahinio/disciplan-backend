"""Auto-generate daily lecture tasks from section meeting times."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from app.db.session import transaction
from app.repositories import task_planner_repo


async def generate_lecture_tasks_for_user(
    user_id: int,
    role_code: str,
    *,
    target_date: date | None = None,
) -> int:
    target_date = target_date or date.today()
    day_id = (target_date.weekday() + 1) % 7  # Python Mon=0 -> DB SUN=0..SAT=6

    created = 0
    async with transaction() as conn:
        routine = await task_planner_repo.list_user_routine(conn, user_id, role_code)
        lecture_type_id = await task_planner_repo.get_planner_type_id(conn, "lecture")

        from app.db.session import fetch_one

        prio_row = await fetch_one(
            conn, "SELECT id FROM task_priorities WHERE code = 'medium' LIMIT 1"
        )
        energy_row = await fetch_one(
            conn, "SELECT id FROM energy_levels WHERE code = 'medium' LIMIT 1"
        )
        if not prio_row or not lecture_type_id:
            return 0

        priority_id = prio_row["id"]
        energy_id = energy_row["id"] if energy_row else None

        for slot in routine:
            if slot.get("day_id") != day_id or not slot.get("meeting_time_id"):
                continue

            meeting_id = slot["meeting_time_id"]
            if await task_planner_repo.lecture_log_exists(
                conn, user_id, meeting_id, target_date
            ):
                continue

            starts: time = slot["starts_at"]
            due_dt = datetime.combine(target_date, starts, tzinfo=timezone.utc)
            title = f"Lecture: {slot['course_code']} Sec {slot['section_label']}"

            task_id = await task_planner_repo.create_planner_task(
                conn,
                user_id=user_id,
                title=title,
                priority_id=priority_id,
                section_id=slot["section_id"],
                planner_task_type_id=lecture_type_id,
                energy_level_id=energy_id,
                due_at=due_dt,
                estimated_effort_min=60,
                source="lecture_auto",
                scheduled_for_date=target_date,
            )
            await task_planner_repo.insert_lecture_log(
                conn,
                user_id=user_id,
                section_id=slot["section_id"],
                meeting_time_id=meeting_id,
                lecture_date=target_date,
                task_id=task_id,
            )
            created += 1

    return created


async def generate_lecture_tasks_for_all_users(*, target_date: date | None = None) -> int:
    target_date = target_date or date.today()
    total = 0
    async with transaction() as conn:
        users = await task_planner_repo.list_active_planner_users(conn)

    for u in users:
        total += await generate_lecture_tasks_for_user(
            u["user_id"], u["role_code"], target_date=target_date
        )
    return total
