"""Planner tasks: weights, reschedule, energy, routine, lecture log."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one

PLANNER_WEIGHT_EXPR = """
    (
        tp.sort_order * 10.0
        * (1.0 + GREATEST(0, TIMESTAMPDIFF(HOUR, UTC_TIMESTAMP(3), COALESCE(ut.due_at, UTC_TIMESTAMP(3)))) / -24.0)
        * (1.0 + (100 - ut.completion_percent) / 100.0)
        * (1.0 + ut.reschedule_count * 0.25)
        * (1.0 + COALESCE(ut.carryover_percent, 0) / 50.0)
        * (1.0 + COALESCE(ut.days_behind, 0) * 0.15)
        * CASE WHEN ut.is_skipped = 1 THEN 0 ELSE 1 END
    )
"""

SCHEDULED_WEIGHT_EXPR = """
    (
        tp.sort_order * 10.0
        * (1.0 + GREATEST(0, TIMESTAMPDIFF(HOUR, UTC_TIMESTAMP(3), COALESCE(ut.occurrence_starts_at, ut.due_at, UTC_TIMESTAMP(3)))) / -12.0)
        * (1.0 + (100 - ut.completion_percent) / 100.0)
        * CASE WHEN ut.is_skipped = 1 THEN 0 ELSE 1 END
    )
"""

WEIGHT_EXPR = f"""
    COALESCE(
        CASE
            WHEN COALESCE(ut.weight_profile, 'planner') = 'scheduled' THEN {SCHEDULED_WEIGHT_EXPR.strip()}
            ELSE {PLANNER_WEIGHT_EXPR.strip()}
        END,
        0
    )
"""

TASK_SELECT = f"""
    SELECT
        ut.id, ut.title, ut.description, ut.due_at, ut.original_due_at,
        ut.is_completed, ut.completed_at, ut.completion_percent,
        ut.estimated_effort_min, ut.computed_weight,
        ut.is_skipped, ut.skipped_at, ut.reschedule_count, ut.source,
        ut.scheduled_for_date, ut.section_id, ut.calendar_event_id,
        ut.event_plan_id, ut.slice_date,
        ut.base_target_percent, ut.carryover_percent, ut.effective_target_percent,
        ut.completed_portion_percent, ut.days_behind, ut.was_skipped_forward,
        ut.weight_profile, ut.occurrence_starts_at, ut.slice_closed,
        ut.attachment_file_id, ut.created_at,
        c.code AS course_code,
        tp.code AS priority_code,
        el.code AS energy_level_code,
        el.sort_order AS energy_sort_order,
        ptt.code AS planner_task_type_code,
        ptt.label AS planner_task_type_label,
        at.code AS task_type_code,
        at.label AS task_type_label,
        af.secure_url AS attachment_url,
        CONCAT(c2.code, '::', s.section_label) AS section_key,
        {WEIGHT_EXPR.strip()} AS live_weight
    FROM user_tasks ut
    LEFT JOIN courses c ON c.id = ut.course_id
    LEFT JOIN sections s ON s.id = ut.section_id
    LEFT JOIN courses c2 ON c2.id = s.course_id
    INNER JOIN task_priorities tp ON tp.id = ut.priority_id
    LEFT JOIN energy_levels el ON el.id = ut.energy_level_id
    LEFT JOIN planner_task_types ptt ON ptt.id = ut.planner_task_type_id
    LEFT JOIN assessment_types at ON at.id = ut.assessment_type_id
    LEFT JOIN files af ON af.id = ut.attachment_file_id AND af.deleted_at IS NULL
"""


async def reschedule_overdue_tasks(conn: pymysql.Connection, user_id: int) -> int:
    """Roll overdue incomplete tasks to tomorrow; bump reschedule_count."""
    return await execute(
        conn,
        """
        UPDATE user_tasks
        SET
            reschedule_count = reschedule_count + 1,
            due_at = DATE_ADD(
                COALESCE(due_at, UTC_TIMESTAMP(3)),
                INTERVAL 1 DAY
            ),
            scheduled_for_date = DATE_ADD(COALESCE(scheduled_for_date, DATE(UTC_TIMESTAMP(3))), INTERVAL 1 DAY),
            original_due_at = COALESCE(original_due_at, due_at),
            source = CASE WHEN source = 'lecture_auto' THEN source ELSE 'reschedule' END
        WHERE user_id = %s
          AND is_completed = 0
          AND is_skipped = 0
          AND completion_percent < 100
          AND due_at IS NOT NULL
          AND due_at < UTC_TIMESTAMP(3)
          AND source NOT IN ('event_slice', 'grading_linked', 'recurring_occurrence', 'one_time')
          AND COALESCE(weight_profile, 'planner') = 'planner'
          AND event_plan_id IS NULL
        """,
        (user_id,),
    )


async def recompute_weights(conn: pymysql.Connection, user_id: int) -> None:
    await execute(
        conn,
        f"""
        UPDATE user_tasks ut
        INNER JOIN task_priorities tp ON tp.id = ut.priority_id
        SET ut.computed_weight = {WEIGHT_EXPR}
        WHERE ut.user_id = %s
        """,
        (user_id,),
    )


async def maintain_tasks_for_user(conn: pymysql.Connection, user_id: int) -> None:
    """Best-effort rollover/reschedule — must not block task reads on lock contention."""
    try:
        await reschedule_overdue_tasks(conn, user_id)
    except Exception:
        pass


async def list_tasks_for_day(
    conn: pymysql.Connection,
    user_id: int,
    *,
    target_date: date,
    user_energy_sort: int | None = None,
    maintain: bool = True,
) -> list[dict[str, Any]]:
    if maintain:
        await maintain_tasks_for_user(conn, user_id)

    order = "ut.is_completed ASC, live_weight DESC, ut.due_at ASC, ut.id ASC"
    if user_energy_sort is not None:
        order = (
            "ut.is_completed ASC, "
            f"ABS(COALESCE(el.sort_order, 2) - {int(user_energy_sort)}) ASC, "
            "live_weight DESC, ut.due_at ASC, ut.id ASC"
        )

    return await fetch_all(
        conn,
        f"""
        {TASK_SELECT}
        WHERE ut.user_id = %s
          AND ut.is_skipped = 0
          AND (
            ut.scheduled_for_date = %s
            OR (ut.scheduled_for_date IS NULL AND DATE(ut.due_at) = %s)
            OR (ut.scheduled_for_date IS NULL AND ut.due_at IS NULL AND ut.is_completed = 0)
          )
        ORDER BY {order}
        """,
        (user_id, target_date, target_date),
    )


async def get_task(conn: pymysql.Connection, user_id: int, task_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        f"""
        {TASK_SELECT}
        WHERE ut.user_id = %s AND ut.id = %s
        """,
        (user_id, task_id),
    )


async def list_all_tasks(conn: pymysql.Connection, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        f"""
        {TASK_SELECT}
        WHERE ut.user_id = %s
        ORDER BY ut.is_completed ASC, live_weight DESC, ut.due_at ASC
        """,
        (user_id,),
    )


async def get_planner_type_id(conn: pymysql.Connection, code: str) -> int | None:
    row = await fetch_one(conn, "SELECT id FROM planner_task_types WHERE code = %s", (code,))
    return row["id"] if row else None


async def create_planner_task(
    conn: pymysql.Connection,
    *,
    user_id: int,
    title: str,
    priority_id: int,
    course_id: int | None = None,
    section_id: int | None = None,
    planner_task_type_id: int | None = None,
    assessment_type_id: int | None = None,
    energy_level_id: int | None = None,
    description: str | None = None,
    due_at: datetime | None = None,
    estimated_effort_min: int | None = None,
    attachment_file_id: int | None = None,
    source: str = "manual",
    scheduled_for_date: date | None = None,
    calendar_event_id: int | None = None,
) -> int:
    sched = scheduled_for_date or (due_at.date() if due_at else date.today())
    original = due_at
    task_id = await execute_returning_id(
        conn,
        """
        INSERT INTO user_tasks (
            user_id, course_id, section_id, assessment_type_id, planner_task_type_id,
            title, description, attachment_file_id, priority_id, energy_level_id,
            estimated_effort_min, due_at, original_due_at, scheduled_for_date,
            source, calendar_event_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            course_id,
            section_id,
            assessment_type_id,
            planner_task_type_id,
            title,
            description,
            attachment_file_id,
            priority_id,
            energy_level_id,
            estimated_effort_min,
            due_at,
            original,
            sched,
            source,
            calendar_event_id,
        ),
    )
    await recompute_weights(conn, user_id)
    return task_id


async def update_planner_task(
    conn: pymysql.Connection,
    user_id: int,
    task_id: int,
    **fields: Any,
) -> bool:
    allowed = {
        "title",
        "description",
        "course_id",
        "section_id",
        "priority_id",
        "energy_level_id",
        "planner_task_type_id",
        "due_at",
        "estimated_effort_min",
        "completion_percent",
        "is_completed",
        "completed_at",
        "is_skipped",
        "skipped_at",
        "attachment_file_id",
        "scheduled_for_date",
        "calendar_event_id",
        "completed_portion_percent",
        "slice_closed",
        "base_target_percent",
        "carryover_percent",
        "effective_target_percent",
        "days_behind",
        "was_skipped_forward",
        "weight_profile",
        "occurrence_starts_at",
        "event_plan_id",
        "slice_date",
    }
    sets: list[str] = []
    params: list[Any] = []
    for key, val in fields.items():
        if key in allowed and val is not ...:
            sets.append(f"{key} = %s")
            params.append(val)
    if not sets:
        return True
    params.extend([task_id, user_id])
    count = await execute(
        conn,
        f"UPDATE user_tasks SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    if count:
        await recompute_weights(conn, user_id)
    return count > 0


async def set_daily_energy(
    conn: pymysql.Connection, user_id: int, energy_date: date, energy_level_id: int
) -> None:
    await execute(
        conn,
        """
        INSERT INTO user_daily_energy (user_id, energy_date, energy_level_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE energy_level_id = VALUES(energy_level_id), set_at = UTC_TIMESTAMP(3)
        """,
        (user_id, energy_date, energy_level_id),
    )


async def get_daily_energy(conn: pymysql.Connection, user_id: int, energy_date: date) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT ude.energy_date, el.code AS energy_level_code, el.sort_order AS energy_sort_order
        FROM user_daily_energy ude
        INNER JOIN energy_levels el ON el.id = ude.energy_level_id
        WHERE ude.user_id = %s AND ude.energy_date = %s
        """,
        (user_id, energy_date),
    )


async def list_user_routine(conn: pymysql.Connection, user_id: int, role_code: str) -> list[dict[str, Any]]:
    base = """
        SELECT
            s.id AS section_id,
            c.code AS course_code,
            c.title AS course_title,
            s.section_label,
            s.room,
            smt.id AS meeting_time_id,
            smt.day_id,
            dow.code AS day_code,
            dow.label AS day_label,
            dow.sort_order AS day_sort_order,
            smt.starts_at,
            smt.ends_at
        FROM sections s
        INNER JOIN courses c ON c.id = s.course_id
        INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
    """
    if role_code == "faculty":
        return await fetch_all(
            conn,
            base
            + """
        INNER JOIN section_faculty sf ON sf.section_id = s.id AND sf.faculty_user_id = %s
        LEFT JOIN section_meeting_times smt ON smt.section_id = s.id
        LEFT JOIN days_of_week dow ON dow.id = smt.day_id
        WHERE s.is_active = 1
        ORDER BY dow.sort_order, smt.starts_at, c.code
        """,
            (user_id,),
        )
    return await fetch_all(
        conn,
        base
        + """
        INNER JOIN section_enrollments se
            ON se.section_id = s.id AND se.student_user_id = %s AND se.dropped_at IS NULL
        LEFT JOIN section_meeting_times smt ON smt.section_id = s.id
        LEFT JOIN days_of_week dow ON dow.id = smt.day_id
        WHERE s.is_active = 1
        ORDER BY dow.sort_order, smt.starts_at, c.code
        """,
        (user_id,),
    )


async def lecture_log_exists(
    conn: pymysql.Connection, user_id: int, meeting_time_id: int, lecture_date: date
) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM user_lecture_task_log
        WHERE user_id = %s AND meeting_time_id = %s AND lecture_date = %s
        """,
        (user_id, meeting_time_id, lecture_date),
    )
    return row is not None


async def insert_lecture_log(
    conn: pymysql.Connection,
    *,
    user_id: int,
    section_id: int,
    meeting_time_id: int,
    lecture_date: date,
    task_id: int,
) -> None:
    await execute(
        conn,
        """
        INSERT IGNORE INTO user_lecture_task_log
            (user_id, section_id, meeting_time_id, lecture_date, task_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, section_id, meeting_time_id, lecture_date, task_id),
    )


async def list_merged_calendar(
    conn: pymysql.Connection, user_id: int, *, from_dt: datetime | None = None
) -> list[dict[str, Any]]:
    params: list[Any] = [user_id]
    date_filter = ""
    if from_dt:
        date_filter = " AND ce.ends_at >= %s"
        params.append(from_dt)

    events = await fetch_all(
        conn,
        f"""
        SELECT ce.id, ce.title, ce.description, ce.starts_at, ce.ends_at, ce.all_day,
               c.code AS course_code, ce.event_plan_id, 'event' AS item_type
        FROM calendar_events ce
        LEFT JOIN courses c ON c.id = ce.course_id
        WHERE ce.owner_user_id = %s {date_filter}
        ORDER BY ce.starts_at ASC
        """,
        tuple(params),
    )

    task_params: list[Any] = [user_id]
    task_filter = ""
    if from_dt:
        task_filter = " AND ut.due_at >= %s"
        task_params.append(from_dt)

    tasks = await fetch_all(
        conn,
        f"""
        SELECT ut.id, ut.title, ut.description,
               ut.due_at AS starts_at,
               DATE_ADD(ut.due_at, INTERVAL COALESCE(ut.estimated_effort_min, 60) MINUTE) AS ends_at,
               0 AS all_day,
               c.code AS course_code,
               ut.event_plan_id,
               'task' AS item_type,
               ut.completion_percent, ut.is_completed, ptt.code AS planner_task_type_code
        FROM user_tasks ut
        LEFT JOIN courses c ON c.id = ut.course_id
        LEFT JOIN planner_task_types ptt ON ptt.id = ut.planner_task_type_id
        WHERE ut.user_id = %s AND ut.due_at IS NOT NULL AND ut.is_skipped = 0 {task_filter}
        ORDER BY ut.due_at ASC
        """,
        tuple(task_params),
    )
    return list(events) + list(tasks)


async def list_active_planner_users(conn: pymysql.Connection) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT DISTINCT u.id AS user_id, r.code AS role_code
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_statuses us ON us.id = u.status_id
        WHERE us.code = 'active' AND r.code IN ('student', 'faculty')
        """,
    )
