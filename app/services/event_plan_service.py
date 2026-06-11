"""Event plan orchestration — divide, recurrence, grading sync."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one, transaction
from app.repositories import dashboard_repo, event_plan_repo, notification_repo, task_planner_repo
from app.services.task_planner_service import _resolve_ids


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _weight_profile(mode: str) -> str:
    if mode in ("one_time", "recurring_weekly"):
        return "scheduled"
    return "planner"


def _days_remaining(today: date, deadline: date) -> int:
    return max(1, (deadline - today).days + 1)


async def get_daily_task_counts(conn, user_id: int, start_date: date, end_date: date) -> dict[date, int]:
    rows = await fetch_all(
        conn,
        """
        SELECT COALESCE(scheduled_for_date, DATE(due_at)) AS task_date, COUNT(*) AS cnt
        FROM user_tasks
        WHERE user_id = %s
          AND is_completed = 0
          AND is_skipped = 0
          AND (
            scheduled_for_date BETWEEN %s AND %s
            OR (scheduled_for_date IS NULL AND DATE(due_at) BETWEEN %s AND %s)
          )
        GROUP BY task_date
        """,
        (user_id, start_date, end_date, start_date, end_date),
    )
    res = {}
    for r in rows:
        d = r.get("task_date")
        if d:
            if isinstance(d, datetime):
                d = d.date()
            res[d] = int(r["cnt"])
    return res


async def _schedule_divided_tasks(
    conn,
    *,
    user_id: int,
    plan_id: int,
    plan: dict,
    title: str,
    deadline_at: datetime,
    priority_id: int,
    energy_level_id: int | None,
    planner_task_type_id: int | None,
    course_id: int | None,
    section_id: int | None,
    estimated_effort_min: int | None,
) -> None:
    import math
    today = date.today()
    deadline_date = deadline_at.date()
    days_rem = (deadline_date - today).days + 1

    if days_rem <= 0:
        N = 1
        selected_dates = [today]
    elif days_rem <= 5:
        N = days_rem
        selected_dates = [today + timedelta(days=i) for i in range(days_rem)]
    else:
        N = 5
        all_candidates = [today + timedelta(days=i) for i in range(days_rem)]
        counts = await get_daily_task_counts(conn, user_id, today, deadline_date)
        sorted_candidates = sorted(all_candidates, key=lambda d: (counts.get(d, 0), d))
        selected_dates = sorted_candidates[:5]
        selected_dates.sort()

    subtask_effort = None
    if estimated_effort_min is not None:
        subtask_effort = int(math.ceil(estimated_effort_min / N))

    for i, d in enumerate(selected_dates):
        part_title = f"{title} Part {i + 1}"
        due_at = datetime.combine(d, deadline_at.time())
        await _insert_task(
            conn,
            user_id=user_id,
            plan=plan,
            title=part_title,
            due_at=due_at,
            scheduled_for_date=d,
            source="event_slice",
            weight_profile="planner",
            priority_id=priority_id,
            energy_level_id=energy_level_id,
            planner_task_type_id=planner_task_type_id,
            course_id=course_id,
            section_id=section_id,
            estimated_effort_min=subtask_effort,
            event_plan_id=plan_id,
            slice_date=d,
            base_target=100.0 / N,
            carryover=0.0,
            effective_target=100.0 / N,
            completion_percent=0,
            completed_portion=0.0,
        )


def _recurrence_dates(day_of_week: int, start: date, weeks: int = 8) -> list[date]:
    """day_of_week: 0=Sunday per JS convention."""
    py_target = (day_of_week + 6) % 7  # Sun=0 -> 6, Mon=1 -> 0
    out: list[date] = []
    cur = start
    end = start + timedelta(days=weeks * 7)
    while cur <= end:
        if cur.weekday() == py_target:
            out.append(cur)
        cur += timedelta(days=1)
    return out


async def _grading_percent(
    conn, *, section_id: int | None, portal_id: int | None, grade_component_id: int | None
) -> float:
    if not section_id:
        return 0.0
    enrolled = await event_plan_repo.enrolled_count(conn, section_id)
    if enrolled <= 0:
        return 0.0
    if portal_id:
        graded = await event_plan_repo.graded_portal_count(conn, portal_id)
    elif grade_component_id:
        code = await event_plan_repo.get_component_code(conn, grade_component_id)
        graded = (
            await event_plan_repo.graded_component_count(conn, section_id, code)
            if code
            else 0
        )
    else:
        return 0.0
    return min(100.0, round((graded / enrolled) * 100, 2))


async def _insert_task(
    conn,
    *,
    user_id: int,
    plan: dict,
    title: str,
    due_at: datetime | None,
    scheduled_for_date: date,
    source: str,
    weight_profile: str,
    priority_id: int,
    energy_level_id: int | None,
    planner_task_type_id: int | None,
    course_id: int | None,
    section_id: int | None,
    estimated_effort_min: int | None,
    event_plan_id: int | None = None,
    slice_date: date | None = None,
    base_target: float | None = None,
    carryover: float = 0,
    effective_target: float | None = None,
    days_behind: int = 0,
    was_skipped_forward: bool = False,
    occurrence_starts_at: datetime | None = None,
    completion_percent: int = 0,
    completed_portion: float = 0,
    calendar_event_id: int | None = None,
) -> int:
    eff = effective_target if effective_target is not None else (base_target or 100)
    pct = completion_percent
    if weight_profile == "planner" and eff > 0 and completed_portion > 0:
        pct = min(100, int(round((completed_portion / eff) * 100)))

    return await execute_returning_id(
        conn,
        """
        INSERT INTO user_tasks (
            user_id, course_id, section_id, planner_task_type_id,
            title, description, priority_id, energy_level_id,
            estimated_effort_min, due_at, original_due_at, scheduled_for_date,
            source, calendar_event_id, event_plan_id, slice_date,
            base_target_percent, carryover_percent, effective_target_percent,
            completed_portion_percent, days_behind, was_skipped_forward,
            weight_profile, occurrence_starts_at, completion_percent, is_completed
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            user_id,
            course_id,
            section_id,
            planner_task_type_id,
            title,
            plan.get("description"),
            priority_id,
            energy_level_id,
            estimated_effort_min,
            due_at,
            due_at,
            scheduled_for_date,
            source,
            calendar_event_id,
            event_plan_id,
            slice_date,
            base_target,
            carryover,
            eff,
            completed_portion,
            days_behind,
            int(was_skipped_forward),
            weight_profile,
            occurrence_starts_at,
            pct,
            int(pct >= 100),
        ),
    )


async def compute_slice_targets(
    conn, *, plan_id: int, user_id: int, target_date: date, deadline_date: date
) -> tuple[float, float, float, int, bool]:
    """Returns base_target, carryover, effective_target, days_behind, was_skipped_forward."""
    yesterday = target_date - timedelta(days=1)
    carryover = 0.0
    was_skipped_forward = False
    days_behind = await event_plan_repo.count_days_behind(conn, plan_id, user_id, target_date)

    y_slice = await event_plan_repo.get_yesterday_slice(conn, plan_id, user_id, yesterday)
    if y_slice and not y_slice.get("slice_closed"):
        await event_plan_repo.close_slice(conn, y_slice["id"])

    if y_slice:
        eff_y = float(y_slice["effective_target_percent"] or 0)
        done_y = float(y_slice["completed_portion_percent"] or 0)
        if y_slice.get("is_skipped"):
            carryover = max(0.0, eff_y - done_y)
            was_skipped_forward = True
        elif done_y < eff_y:
            carryover = eff_y - done_y

    days_rem = _days_remaining(target_date, deadline_date)
    if target_date >= deadline_date:
        prior_done = await event_plan_repo.sum_completed_portions(conn, plan_id, before_date=target_date)
        base = max(0.0, 100.0 - prior_done)
    else:
        base = 100.0 / days_rem

    effective = min(100.0, base + carryover)
    return base, carryover, effective, days_behind, was_skipped_forward


async def ensure_daily_slices(conn, user_id: int, target_date: date) -> None:
    plans = await fetch_all_active_divide_plans(conn, user_id, target_date)
    for plan in plans:
        plan_id = plan["id"]
        if await event_plan_repo.slice_exists(conn, plan_id, user_id, target_date):
            if plan["scheduling_mode"] == "grading_linked":
                await _sync_grading_plan_task(conn, plan, user_id, target_date)
            continue

        deadline = plan["deadline_at"]
        if not deadline:
            continue
        deadline_date = deadline.date() if isinstance(deadline, datetime) else deadline
        if target_date > deadline_date:
            continue

        base, carryover, effective, days_behind, skipped_fwd = await compute_slice_targets(
            conn,
            plan_id=plan_id,
            user_id=user_id,
            target_date=target_date,
            deadline_date=deadline_date,
        )

        due_at = datetime.combine(
            target_date,
            deadline.time() if isinstance(deadline, datetime) else time(23, 59),
        )
        source = "grading_linked" if plan["scheduling_mode"] == "grading_linked" else "event_slice"
        completion = 0
        portion = 0.0
        if source == "grading_linked":
            completion = int(await _grading_percent(
                conn,
                section_id=plan.get("section_id"),
                portal_id=plan.get("portal_id"),
                grade_component_id=plan.get("grade_component_id"),
            ))
            portion = float(completion)

        await _insert_task(
            conn,
            user_id=user_id,
            plan=plan,
            title=plan["title"],
            due_at=due_at,
            scheduled_for_date=target_date,
            source=source,
            weight_profile="planner",
            priority_id=plan["priority_id"],
            energy_level_id=plan.get("energy_level_id"),
            planner_task_type_id=plan.get("planner_task_type_id"),
            course_id=plan.get("course_id"),
            section_id=plan.get("section_id"),
            estimated_effort_min=plan.get("estimated_effort_min"),
            event_plan_id=plan_id,
            slice_date=target_date,
            base_target=base,
            carryover=carryover,
            effective_target=effective,
            days_behind=days_behind,
            was_skipped_forward=skipped_fwd,
            completion_percent=completion,
            completed_portion=portion,
        )

        if carryover > 0:
            await _notify_backlog(conn, user_id, plan["title"], carryover)

        await _check_plan_completion(conn, plan_id, user_id)

    # Materialize recurring occurrences for today
    await _ensure_recurring_today(conn, user_id, target_date)


async def fetch_all_active_divide_plans(
    conn, user_id: int, target_date: date
) -> list[dict[str, Any]]:
    from app.db.session import fetch_all

    return await fetch_all(
        conn,
        """
        SELECT pep.*, pep.priority_id, pep.energy_level_id, pep.planner_task_type_id
        FROM planner_event_plans pep
        WHERE pep.owner_user_id = %s AND pep.is_active = 1 AND pep.is_completed = 0
          AND pep.scheduling_mode IN ('grading_linked')
          AND pep.deadline_at IS NOT NULL
          AND DATE(pep.deadline_at) >= %s
        """,
        (user_id, target_date),
    )


async def _sync_grading_plan_task(
    conn, plan: dict, user_id: int, target_date: date
) -> None:
    from app.db.session import fetch_one as fo

    row = await fo(
        conn,
        """
        SELECT id FROM user_tasks
        WHERE event_plan_id = %s AND user_id = %s AND slice_date = %s
        LIMIT 1
        """,
        (plan["id"], user_id, target_date),
    )
    if not row:
        return
    pct = int(
        await _grading_percent(
            conn,
            section_id=plan.get("section_id"),
            portal_id=plan.get("portal_id"),
            grade_component_id=plan.get("grade_component_id"),
        )
    )
    await task_planner_repo.update_planner_task(
        conn,
        user_id,
        row["id"],
        completion_percent=pct,
        completed_portion_percent=pct,
        is_completed=int(pct >= 100),
        completed_at=datetime.utcnow() if pct >= 100 else None,
    )
    await event_plan_repo.update_plan_completed_percent(conn, plan["id"], pct)
    if pct >= 100:
        await event_plan_repo.complete_plan(conn, plan["id"])


async def _ensure_recurring_today(conn, user_id: int, target_date: date) -> None:
    from app.db.session import fetch_all

    py_dow = (target_date.weekday() + 1) % 7  # Sun=0
    plans = await fetch_all(
        conn,
        """
        SELECT pep.*, per.day_of_week, per.starts_time, per.duration_min
        FROM planner_event_plans pep
        INNER JOIN planner_event_recurrence per ON per.plan_id = pep.id
        WHERE pep.owner_user_id = %s AND pep.is_active = 1 AND pep.is_completed = 0
          AND pep.scheduling_mode = 'recurring_weekly' AND per.day_of_week = %s
        """,
        (user_id, py_dow),
    )
    for plan in plans:
        if await event_plan_repo.slice_exists(conn, plan["id"], user_id, target_date):
            continue
        st = plan["starts_time"]
        if isinstance(st, timedelta):
            total_seconds = int(st.total_seconds())
            hours = (total_seconds // 3600) % 24
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            st_time = time(hours, minutes, seconds)
        elif isinstance(st, str):
            if ":" in st:
                parts = st.split(":")
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2]) if len(parts) > 2 else 0
                st_time = time(hours, minutes, seconds)
            else:
                st_time = time.fromisoformat(st)
        elif isinstance(st, time):
            st_time = st
        else:
            st_time = time(7, 0)
        occ_start = datetime.combine(target_date, st_time)
        due_at = occ_start + timedelta(minutes=int(plan["duration_min"] or 60))
        await _insert_task(
            conn,
            user_id=user_id,
            plan=plan,
            title=plan["title"],
            due_at=due_at,
            scheduled_for_date=target_date,
            source="recurring_occurrence",
            weight_profile="scheduled",
            priority_id=plan["priority_id"],
            energy_level_id=plan.get("energy_level_id"),
            planner_task_type_id=plan.get("planner_task_type_id"),
            course_id=plan.get("course_id"),
            section_id=plan.get("section_id"),
            estimated_effort_min=plan.get("estimated_effort_min"),
            event_plan_id=plan["id"],
            slice_date=target_date,
            occurrence_starts_at=occ_start,
        )


async def _check_plan_completion(conn, plan_id: int, user_id: int) -> None:
    total = await event_plan_repo.sum_completed_portions(conn, plan_id)
    await event_plan_repo.update_plan_completed_percent(conn, plan_id, total)
    if total >= 100:
        await event_plan_repo.complete_plan(conn, plan_id)
        await event_plan_repo.cancel_future_slices(conn, plan_id, user_id, date.today())


async def _notify_backlog(conn, user_id: int, title: str, carryover: float) -> None:
    try:
        await notification_repo.create_notification(
            conn,
            recipient_user_id=user_id,
            type_code="system",
            title=f"Backlog: {title}",
            body_preview=f"{carryover:.0f}% rolled to today — higher priority",
            action_path="/dashboard",
        )
    except Exception:
        pass


async def create_plan(user_id: int, body) -> dict:
    async with transaction() as conn:
        ids = await _resolve_ids(
            conn,
            priority_code=body.priority_code or "medium",
            energy_level_code=body.energy_level_code,
            planner_task_type_code=body.planner_task_type_code,
            course_code=body.course_code,
            section_key=body.section_key,
        )
        deadline_at = _parse_dt(body.deadline_at) if body.deadline_at else None
        mode = body.scheduling_mode

        portal_id = body.portal_id
        grade_component_id = body.grade_component_id
        if mode == "grading_linked" and grade_component_id and not portal_id:
            comp = await fetch_one(
                conn,
                "SELECT portal_id FROM section_grade_components WHERE id = %s",
                (grade_component_id,),
            )
            if comp and comp.get("portal_id"):
                portal_id = comp["portal_id"]

        plan_id = await event_plan_repo.create_plan(
            conn,
            owner_user_id=user_id,
            title=body.title,
            description=body.description,
            planner_task_type_id=ids.get("planner_task_type_id"),
            course_id=ids.get("course_id"),
            section_id=ids.get("section_id"),
            scheduling_mode=mode,
            deadline_at=deadline_at,
            portal_id=portal_id,
            grade_component_id=grade_component_id,
            priority_id=ids["priority_id"],
            energy_level_id=ids.get("energy_level_id"),
            estimated_effort_min=body.estimated_effort_min,
        )

        cal_id = None
        task_id = None

        if mode == "calendar_only":
            starts = _parse_dt(body.starts_at)
            ends = _parse_dt(body.ends_at) or (starts + timedelta(hours=1) if starts else None)
            if starts and ends:
                cal_id = await dashboard_repo.create_calendar_event(
                    conn,
                    owner_user_id=user_id,
                    title=body.title,
                    starts_at=starts,
                    ends_at=ends,
                    course_id=ids.get("course_id"),
                    description=body.description,
                )
                await execute(
                    conn,
                    "UPDATE calendar_events SET event_plan_id = %s WHERE id = %s",
                    (plan_id, cal_id),
                )

        elif mode == "one_time":
            starts = _parse_dt(body.starts_at)
            if not starts:
                raise HTTPException(400, "starts_at required for one_time")
            sched = starts.date()
            ends = _parse_dt(body.ends_at) or starts + timedelta(minutes=body.estimated_effort_min or 60)
            cal_id = await dashboard_repo.create_calendar_event(
                conn,
                owner_user_id=user_id,
                title=body.title,
                starts_at=starts,
                ends_at=ends,
                course_id=ids.get("course_id"),
                description=body.description,
            )
            await execute(conn, "UPDATE calendar_events SET event_plan_id = %s WHERE id = %s", (plan_id, cal_id))
            task_id = await _insert_task(
                conn,
                user_id=user_id,
                plan={"description": body.description},
                title=body.title,
                due_at=starts,
                scheduled_for_date=sched,
                source="one_time",
                weight_profile="scheduled",
                priority_id=ids["priority_id"],
                energy_level_id=ids.get("energy_level_id"),
                planner_task_type_id=ids.get("planner_task_type_id"),
                course_id=ids.get("course_id"),
                section_id=ids.get("section_id"),
                estimated_effort_min=body.estimated_effort_min,
                event_plan_id=plan_id,
                slice_date=sched,
                occurrence_starts_at=starts,
                calendar_event_id=cal_id,
            )

        elif mode == "recurring_weekly":
            if not body.recurrence:
                raise HTTPException(400, "recurrence required")
            today = date.today()
            for slot in body.recurrence:
                await event_plan_repo.add_recurrence(
                    conn,
                    plan_id=plan_id,
                    day_of_week=slot.day_of_week,
                    starts_time=time.fromisoformat(slot.starts_time),
                    duration_min=slot.duration_min,
                )
                for occ_date in _recurrence_dates(slot.day_of_week, today):
                    st = time.fromisoformat(slot.starts_time)
                    occ_start = datetime.combine(occ_date, st)
                    occ_end = occ_start + timedelta(minutes=slot.duration_min)
                    cid = await dashboard_repo.create_calendar_event(
                        conn,
                        owner_user_id=user_id,
                        title=body.title,
                        starts_at=occ_start,
                        ends_at=occ_end,
                        course_id=ids.get("course_id"),
                        description=body.description,
                    )
                    await execute(
                        conn,
                        "UPDATE calendar_events SET event_plan_id = %s, is_recurring_instance = 1 WHERE id = %s",
                        (plan_id, cid),
                    )

        elif mode in ("deadline_divide", "grading_linked"):
            if not deadline_at:
                raise HTTPException(400, "deadline_at required")
            cal_id = await dashboard_repo.create_calendar_event(
                conn,
                owner_user_id=user_id,
                title=body.title,
                starts_at=deadline_at,
                ends_at=deadline_at,
                course_id=ids.get("course_id"),
                description=body.description,
            )
            await execute(conn, "UPDATE calendar_events SET event_plan_id = %s WHERE id = %s", (plan_id, cal_id))
            if mode == "deadline_divide":
                await _schedule_divided_tasks(
                    conn,
                    user_id=user_id,
                    plan_id=plan_id,
                    plan={"description": body.description},
                    title=body.title,
                    deadline_at=deadline_at,
                    priority_id=ids["priority_id"],
                    energy_level_id=ids.get("energy_level_id"),
                    planner_task_type_id=ids.get("planner_task_type_id"),
                    course_id=ids.get("course_id"),
                    section_id=ids.get("section_id"),
                    estimated_effort_min=body.estimated_effort_min,
                )
            else:
                await ensure_daily_slices(conn, user_id, date.today())

        await task_planner_repo.recompute_weights(conn, user_id)
        return {"id": plan_id, "calendar_event_id": cal_id, "task_id": task_id}


async def update_slice_progress(user_id: int, task_id: int, portion: float) -> None:
    async with transaction() as conn:
        task = await task_planner_repo.get_task(conn, user_id, task_id)
        if not task or task.get("source") not in ("event_slice",):
            raise HTTPException(404, "Slice task not found")
        eff = float(task.get("effective_target_percent") or 100)
        portion = max(0.0, min(portion, eff))
        pct = min(100, int(round((portion / eff) * 100))) if eff > 0 else 0
        await task_planner_repo.update_planner_task(
            conn,
            user_id,
            task_id,
            completed_portion_percent=portion,
            completion_percent=pct,
            is_completed=int(pct >= 100),
            completed_at=datetime.utcnow() if pct >= 100 else None,
        )
        if task.get("event_plan_id"):
            await _check_plan_completion(conn, int(task["event_plan_id"]), user_id)
        await task_planner_repo.recompute_weights(conn, user_id)


async def skip_slice_task(user_id: int, task_id: int) -> None:
    async with transaction() as conn:
        task = await task_planner_repo.get_task(conn, user_id, task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.get("source") == "grading_linked":
            raise HTTPException(400, "Grading tasks cannot be skipped")
        profile = task.get("weight_profile") or "planner"
        await task_planner_repo.update_planner_task(
            conn,
            user_id,
            task_id,
            is_skipped=1,
            skipped_at=datetime.utcnow(),
            slice_closed=1,
        )
        if profile == "scheduled":
            await task_planner_repo.recompute_weights(conn, user_id)
            return
        # planner: carryover handled on next ensure_daily_slices
        await task_planner_repo.recompute_weights(conn, user_id)


async def list_plans(user_id: int) -> list[dict]:
    async with transaction() as conn:
        plans = await event_plan_repo.list_active_plans(conn, user_id)
        plan_ids = {int(p["id"]) for p in plans}
        if plan_ids:
            placeholders = ",".join(["%s"] * len(plan_ids))
            orphan_tasks = await fetch_all(
                conn,
                f"""
                SELECT DISTINCT ut.event_plan_id
                FROM user_tasks ut
                INNER JOIN planner_event_plans pep ON pep.id = ut.event_plan_id
                WHERE ut.user_id = %s AND ut.event_plan_id IS NOT NULL
                  AND ut.event_plan_id NOT IN ({placeholders})
                  AND pep.owner_user_id = %s AND pep.is_active = 1 AND pep.is_completed = 0
                  AND pep.deadline_at IS NOT NULL AND DATE(pep.deadline_at) >= CURDATE()
                """,
                (user_id, *plan_ids, user_id),
            )
        else:
            orphan_tasks = await fetch_all(
                conn,
                """
                SELECT DISTINCT ut.event_plan_id
                FROM user_tasks ut
                INNER JOIN planner_event_plans pep ON pep.id = ut.event_plan_id
                WHERE ut.user_id = %s AND ut.event_plan_id IS NOT NULL
                  AND pep.owner_user_id = %s AND pep.is_active = 1 AND pep.is_completed = 0
                  AND pep.deadline_at IS NOT NULL AND DATE(pep.deadline_at) >= CURDATE()
                """,
                (user_id, user_id),
            )
        for row in orphan_tasks:
            pid = int(row["event_plan_id"])
            extra = await event_plan_repo.get_plan(conn, pid, user_id)
            if extra and extra.get("is_active") and not extra.get("is_completed"):
                plans.append(
                    {
                        "id": extra["id"],
                        "title": extra["title"],
                        "scheduling_mode": extra["scheduling_mode"],
                        "deadline_at": extra["deadline_at"],
                        "plan_completed_percent": extra.get("plan_completed_percent", 0),
                        "is_completed": extra.get("is_completed", 0),
                        "planner_task_type_code": extra.get("planner_task_type_code"),
                        "course_code": extra.get("course_code"),
                    }
                )
        plans.sort(
            key=lambda p: (
                p.get("deadline_at") or datetime.max,
                p.get("id") or 0,
            )
        )
        return plans


async def get_plan_detail(user_id: int, plan_id: int) -> dict:
    async with transaction() as conn:
        plan = await event_plan_repo.get_plan(conn, plan_id, user_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        plan["recurrence"] = await event_plan_repo.list_recurrence(conn, plan_id)
        if plan.get("scheduling_mode") in ("one_time", "calendar_only"):
            cal = await fetch_one(
                conn,
                """
                SELECT starts_at, ends_at
                FROM calendar_events
                WHERE event_plan_id = %s AND owner_user_id = %s
                ORDER BY starts_at ASC
                LIMIT 1
                """,
                (plan_id, user_id),
            )
            if cal:
                plan["starts_at"] = cal.get("starts_at")
                plan["ends_at"] = cal.get("ends_at")
        return plan


async def update_plan(user_id: int, plan_id: int, body) -> dict:
    async with transaction() as conn:
        existing = await event_plan_repo.get_plan(conn, plan_id, user_id)
        if not existing or not existing.get("is_active"):
            raise HTTPException(404, "Plan not found")

        priority_code = body.priority_code or existing.get("priority_code") or "medium"
        energy_code = (
            body.energy_level_code
            if body.energy_level_code is not None
            else existing.get("energy_level_code")
        )
        type_code = body.planner_task_type_code or existing.get("planner_task_type_code")
        course_code = body.course_code if body.course_code is not None else existing.get("course_code")
        section_key = body.section_key
        if section_key is None and existing.get("course_code") and existing.get("section_label"):
            section_key = f"{existing['course_code']}::{existing['section_label']}"

        ids = await _resolve_ids(
            conn,
            priority_code=priority_code,
            energy_level_code=energy_code,
            planner_task_type_code=type_code,
            course_code=course_code,
            section_key=section_key,
        )

        portal_id = body.portal_id if body.portal_id is not None else existing.get("portal_id")
        grade_component_id = (
            body.grade_component_id
            if body.grade_component_id is not None
            else existing.get("grade_component_id")
        )
        if existing.get("scheduling_mode") == "grading_linked" and grade_component_id and not portal_id:
            comp = await fetch_one(
                conn,
                "SELECT portal_id FROM section_grade_components WHERE id = %s",
                (grade_component_id,),
            )
            if comp and comp.get("portal_id"):
                portal_id = comp["portal_id"]

        deadline_at = (
            _parse_dt(body.deadline_at)
            if body.deadline_at
            else existing.get("deadline_at")
        )
        starts_at = _parse_dt(body.starts_at) if body.starts_at else None
        ends_at = _parse_dt(body.ends_at) if body.ends_at else None

        clear_course = body.course_code == ""
        clear_section = body.section_key == ""
        clear_energy = body.energy_level_code == ""

        ok = await event_plan_repo.update_plan_fields(
            conn,
            plan_id,
            user_id,
            title=body.title,
            description=body.description,
            planner_task_type_id=ids.get("planner_task_type_id"),
            course_id=ids.get("course_id"),
            section_id=ids.get("section_id"),
            deadline_at=deadline_at if body.deadline_at else None,
            portal_id=portal_id,
            grade_component_id=grade_component_id,
            priority_id=ids["priority_id"],
            energy_level_id=ids.get("energy_level_id"),
            estimated_effort_min=body.estimated_effort_min,
            clear_course=clear_course,
            clear_section=clear_section,
            clear_energy=clear_energy,
        )
        if not ok:
            raise HTTPException(404, "Plan not found")

        cal_deadline = deadline_at if body.deadline_at else None
        if starts_at and existing.get("scheduling_mode") in ("one_time", "calendar_only"):
            cal_deadline = starts_at

        await event_plan_repo.propagate_plan_metadata(
            conn,
            plan_id,
            user_id,
            title=body.title,
            description=body.description,
            course_id=ids.get("course_id"),
            section_id=ids.get("section_id"),
            priority_id=ids["priority_id"],
            energy_level_id=ids.get("energy_level_id"),
            estimated_effort_min=body.estimated_effort_min,
            deadline_at=cal_deadline,
            clear_course=clear_course,
            clear_section=clear_section,
            clear_energy=clear_energy,
        )

        mode = existing.get("scheduling_mode")
        if mode in ("one_time", "calendar_only") and starts_at:
            await execute(
                conn,
                """
                UPDATE calendar_events
                SET starts_at = %s, ends_at = %s
                WHERE event_plan_id = %s AND owner_user_id = %s
                """,
                (
                    starts_at,
                    ends_at or starts_at + timedelta(minutes=body.estimated_effort_min or 60),
                    plan_id,
                    user_id,
                ),
            )
            await execute(
                conn,
                """
                UPDATE user_tasks
                SET due_at = %s, original_due_at = %s, occurrence_starts_at = %s
                WHERE event_plan_id = %s AND user_id = %s AND source = 'one_time'
                """,
                (starts_at, starts_at, starts_at, plan_id, user_id),
            )

        if body.recurrence and mode == "recurring_weekly":
            await event_plan_repo.clear_recurrence(conn, plan_id)
            for slot in body.recurrence:
                await event_plan_repo.add_recurrence(
                    conn,
                    plan_id=plan_id,
                    day_of_week=slot.day_of_week,
                    starts_time=time.fromisoformat(slot.starts_time),
                    duration_min=slot.duration_min,
                )

        await task_planner_repo.recompute_weights(conn, user_id)
        return {"id": plan_id}


async def delete_plan(user_id: int, plan_id: int) -> None:
    async with transaction() as conn:
        ok = await event_plan_repo.soft_delete_plan(conn, plan_id, user_id)
        if not ok:
            raise HTTPException(404, "Plan not found")
        await event_plan_repo.cancel_future_slices(conn, plan_id, user_id, date.today())
        await event_plan_repo.skip_all_open_tasks(conn, plan_id, user_id)
        await event_plan_repo.delete_calendar_for_plan(conn, plan_id, user_id)
        await task_planner_repo.recompute_weights(conn, user_id)
