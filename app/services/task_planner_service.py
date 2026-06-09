"""Task planner orchestration for dashboard API."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import HTTPException, status

from app.db.session import fetch_one, get_connection, transaction
from app.repositories import academic_repo, dashboard_repo, task_planner_repo


async def _resolve_ids(
    conn,
    *,
    priority_code: str = "medium",
    energy_level_code: str | None = None,
    planner_task_type_code: str | None = None,
    task_type_code: str | None = None,
    course_code: str | None = None,
    section_key: str | None = None,
) -> dict:
    priority = await fetch_one(
        conn, "SELECT id FROM task_priorities WHERE code = %s", (priority_code,)
    )
    if not priority:
        raise HTTPException(status_code=400, detail="Invalid priority")

    energy_id = None
    if energy_level_code:
        e = await fetch_one(
            conn, "SELECT id FROM energy_levels WHERE code = %s", (energy_level_code,)
        )
        energy_id = e["id"] if e else None

    planner_type_id = None
    if planner_task_type_code:
        planner_type_id = await task_planner_repo.get_planner_type_id(
            conn, planner_task_type_code
        )

    assessment_type_id = None
    if task_type_code:
        at = await fetch_one(
            conn, "SELECT id FROM assessment_types WHERE code = %s", (task_type_code,)
        )
        assessment_type_id = at["id"] if at else None

    course_id = None
    section_id = None
    if course_code:
        course = await academic_repo.get_course_by_code(conn, course_code)
        course_id = course["id"] if course else None
    if section_key and "::" in section_key:
        cc, sl = section_key.split("::", 1)
        sec = await academic_repo.find_section(conn, cc, sl)
        if sec:
            section_id = sec["id"]
            course_id = course_id or sec["course_id"]

    return {
        "priority_id": priority["id"],
        "energy_level_id": energy_id,
        "planner_task_type_id": planner_type_id,
        "assessment_type_id": assessment_type_id,
        "course_id": course_id,
        "section_id": section_id,
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def list_today(user_id: int, role_code: str, *, target_date: date | None = None) -> list[dict]:
    from app.services import event_plan_service

    target_date = target_date or date.today()
    # Commit slice materialization before reads to avoid long-lived row locks.
    async with transaction() as conn:
        await event_plan_service.ensure_daily_slices(conn, user_id, target_date)

    async with transaction() as conn:
        await task_planner_repo.maintain_tasks_for_user(conn, user_id)

    async with get_connection() as conn:
        energy = await task_planner_repo.get_daily_energy(conn, user_id, target_date)
        energy_sort = energy["energy_sort_order"] if energy else None
        return await task_planner_repo.list_tasks_for_day(
            conn,
            user_id,
            target_date=target_date,
            user_energy_sort=energy_sort,
            maintain=False,
        )


async def get_task(user_id: int, task_id: int) -> dict:
    async with transaction() as conn:
        task = await task_planner_repo.get_task(conn, user_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def create_task_from_calendar_event(
    conn,
    *,
    user_id: int,
    event_id: int,
    title: str,
    starts_at: datetime,
    description: str | None = None,
    course_code: str | None = None,
    section_key: str | None = None,
    planner_task_type_code: str | None = None,
    priority_code: str = "medium",
    energy_level_code: str | None = None,
    estimated_effort_min: int | None = None,
) -> int:
    ids = await _resolve_ids(
        conn,
        priority_code=priority_code,
        energy_level_code=energy_level_code,
        planner_task_type_code=planner_task_type_code or "personal",
        course_code=course_code,
        section_key=section_key,
    )
    return await task_planner_repo.create_planner_task(
        conn,
        user_id=user_id,
        title=title,
        description=description,
        due_at=starts_at,
        estimated_effort_min=estimated_effort_min,
        source="event_auto",
        calendar_event_id=event_id,
        **ids,
    )


async def create_task(user_id: int, body) -> int:
    async with transaction() as conn:
        ids = await _resolve_ids(
            conn,
            priority_code=body.priority_code,
            energy_level_code=body.energy_level_code,
            planner_task_type_code=body.planner_task_type_code or body.task_type_code,
            task_type_code=body.task_type_code if not body.planner_task_type_code else None,
            course_code=body.course_code,
            section_key=body.section_key,
        )
        due_at = _parse_dt(body.due_at)
        return await task_planner_repo.create_planner_task(
            conn,
            user_id=user_id,
            title=body.title,
            description=body.description,
            due_at=due_at,
            estimated_effort_min=body.estimated_effort_min,
            attachment_file_id=body.attachment_file_id,
            source="manual",
            **ids,
        )


async def update_task(user_id: int, task_id: int, body) -> None:
    from app.services import event_plan_service, gamification_service

    async with transaction() as conn:
        task = await task_planner_repo.get_task(conn, user_id, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        was_completed = int(task.get("is_completed") or 0) == 1

        if body.skipped is not None and body.skipped:
            if task.get("source") in ("event_slice", "recurring_occurrence", "one_time", "grading_linked"):
                await event_plan_service.skip_slice_task(user_id, task_id)
                return

        if task.get("source") == "event_slice":
            eff = float(task.get("effective_target_percent") or 100)
            if body.completed_portion_percent is not None:
                portion = float(body.completed_portion_percent)
            elif body.completed is True:
                portion = eff
            elif body.completed is False:
                portion = 0.0
            elif body.completion_percent is not None:
                portion = (body.completion_percent / 100.0) * eff
            else:
                portion = None
            if portion is not None:
                await event_plan_service.update_slice_progress(user_id, task_id, portion)
                return

        if body.completed is not None:
            pct = 100 if body.completed else (body.completion_percent or 0)
            await task_planner_repo.update_planner_task(
                conn,
                user_id,
                task_id,
                is_completed=int(body.completed),
                completed_at=datetime.now(timezone.utc) if body.completed else None,
                completion_percent=pct,
            )

        if body.skipped is not None:
            await task_planner_repo.update_planner_task(
                conn,
                user_id,
                task_id,
                is_skipped=int(body.skipped),
                skipped_at=datetime.now(timezone.utc) if body.skipped else None,
            )

        if body.completion_percent is not None and body.completed is None:
            pct = max(0, min(100, body.completion_percent))
            await task_planner_repo.update_planner_task(
                conn,
                user_id,
                task_id,
                completion_percent=pct,
                is_completed=int(pct >= 100),
                completed_at=datetime.now(timezone.utc) if pct >= 100 else None,
            )

        ids = {}
        if any(
            getattr(body, f, None) is not None
            for f in ("priority_code", "energy_level_code", "planner_task_type_code", "course_code", "section_key")
        ):
            resolved = await _resolve_ids(
                conn,
                priority_code=body.priority_code or "medium",
                energy_level_code=body.energy_level_code,
                planner_task_type_code=body.planner_task_type_code,
                course_code=body.course_code,
                section_key=body.section_key,
            )
            ids = resolved

        fields: dict = {}
        if body.title is not None:
            fields["title"] = body.title
        if body.description is not None:
            fields["description"] = body.description
        if body.due_at is not None:
            fields["due_at"] = _parse_dt(body.due_at)
        if body.estimated_effort_min is not None:
            fields["estimated_effort_min"] = body.estimated_effort_min
        if body.attachment_file_id is not None:
            fields["attachment_file_id"] = body.attachment_file_id
        fields.update(ids)
        if fields:
            await task_planner_repo.update_planner_task(conn, user_id, task_id, **fields)

        updated = await task_planner_repo.get_task(conn, user_id, task_id)
        if (
            updated
            and not was_completed
            and int(updated.get("is_completed") or 0) == 1
            and int(updated.get("completion_percent") or 0) >= 100
        ):
            await gamification_service.on_task_completed(conn, user_id, task_id)


async def delete_task(user_id: int, task_id: int) -> None:
    async with transaction() as conn:
        ok = await dashboard_repo.delete_task(conn, user_id, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")


async def set_energy(user_id: int, energy_code: str, energy_date: date | None = None) -> None:
    energy_date = energy_date or date.today()
    async with transaction() as conn:
        row = await fetch_one(
            conn, "SELECT id FROM energy_levels WHERE code = %s", (energy_code,)
        )
        if not row:
            raise HTTPException(status_code=400, detail="Invalid energy level")
        await task_planner_repo.set_daily_energy(conn, user_id, energy_date, row["id"])


async def get_energy(user_id: int, energy_date: date | None = None) -> dict | None:
    energy_date = energy_date or date.today()
    async with transaction() as conn:
        return await task_planner_repo.get_daily_energy(conn, user_id, energy_date)


async def get_routine(user_id: int, role_code: str) -> list[dict]:
    async with transaction() as conn:
        return await task_planner_repo.list_user_routine(conn, user_id, role_code)


async def merged_calendar(user_id: int, from_dt: datetime | None = None) -> list[dict]:
    async with transaction() as conn:
        return await task_planner_repo.list_merged_calendar(conn, user_id, from_dt=from_dt)
