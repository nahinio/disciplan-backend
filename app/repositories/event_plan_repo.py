"""Planner event plans — raw SQL."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def create_plan(
    conn: pymysql.Connection,
    *,
    owner_user_id: int,
    title: str,
    description: str | None,
    planner_task_type_id: int | None,
    course_id: int | None,
    section_id: int | None,
    scheduling_mode: str,
    deadline_at: datetime | None,
    portal_id: int | None,
    grade_component_id: int | None,
    priority_id: int,
    energy_level_id: int | None,
    estimated_effort_min: int | None,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO planner_event_plans (
            owner_user_id, title, description, planner_task_type_id,
            course_id, section_id, scheduling_mode, deadline_at,
            portal_id, grade_component_id, priority_id, energy_level_id,
            estimated_effort_min
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            owner_user_id,
            title,
            description,
            planner_task_type_id,
            course_id,
            section_id,
            scheduling_mode,
            deadline_at,
            portal_id,
            grade_component_id,
            priority_id,
            energy_level_id,
            estimated_effort_min,
        ),
    )


async def add_recurrence(
    conn: pymysql.Connection,
    *,
    plan_id: int,
    day_of_week: int,
    starts_time: time,
    duration_min: int,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO planner_event_recurrence (plan_id, day_of_week, starts_time, duration_min)
        VALUES (%s, %s, %s, %s)
        """,
        (plan_id, day_of_week, starts_time, duration_min),
    )


async def get_plan(conn: pymysql.Connection, plan_id: int, owner_user_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT
            pep.id, pep.owner_user_id, pep.title, pep.description,
            pep.scheduling_mode, pep.deadline_at, pep.portal_id, pep.grade_component_id,
            pep.course_id, pep.section_id, pep.estimated_effort_min,
            pep.plan_completed_percent, pep.is_active, pep.is_completed, pep.completed_at,
            pep.created_at,
            ptt.code AS planner_task_type_code,
            ptt.label AS planner_task_type_label,
            tp.code AS priority_code,
            el.code AS energy_level_code,
            c.code AS course_code,
            s.section_label
        FROM planner_event_plans pep
        LEFT JOIN planner_task_types ptt ON ptt.id = pep.planner_task_type_id
        INNER JOIN task_priorities tp ON tp.id = pep.priority_id
        LEFT JOIN energy_levels el ON el.id = pep.energy_level_id
        LEFT JOIN courses c ON c.id = pep.course_id
        LEFT JOIN sections s ON s.id = pep.section_id
        WHERE pep.id = %s AND pep.owner_user_id = %s
        """,
        (plan_id, owner_user_id),
    )


async def expire_past_deadline_plans(conn: pymysql.Connection, owner_user_id: int) -> None:
    await execute(
        conn,
        """
        UPDATE planner_event_plans
        SET is_active = 0
        WHERE owner_user_id = %s AND is_active = 1
          AND deadline_at IS NOT NULL
          AND DATE(deadline_at) < CURDATE()
        """,
        (owner_user_id,),
    )


async def list_active_plans(conn: pymysql.Connection, owner_user_id: int) -> list[dict[str, Any]]:
    await expire_past_deadline_plans(conn, owner_user_id)
    return await fetch_all(
        conn,
        """
        SELECT
            pep.id, pep.title, pep.scheduling_mode, pep.deadline_at,
            pep.plan_completed_percent, pep.is_completed,
            ptt.code AS planner_task_type_code,
            c.code AS course_code
        FROM planner_event_plans pep
        LEFT JOIN planner_task_types ptt ON ptt.id = pep.planner_task_type_id
        LEFT JOIN courses c ON c.id = pep.course_id
        WHERE pep.owner_user_id = %s AND pep.is_active = 1
          AND (
            pep.is_completed = 0
            OR (
              pep.is_completed = 1
              AND pep.completed_at IS NOT NULL
              AND DATE(pep.completed_at) = CURDATE()
            )
          )
          AND (
            pep.deadline_at IS NULL
            OR DATE(pep.deadline_at) >= CURDATE()
          )
        ORDER BY pep.deadline_at ASC, pep.created_at DESC
        """,
        (owner_user_id,),
    )


async def soft_delete_plan(conn: pymysql.Connection, plan_id: int, owner_user_id: int) -> bool:
    count = await execute(
        conn,
        "UPDATE planner_event_plans SET is_active = 0 WHERE id = %s AND owner_user_id = %s",
        (plan_id, owner_user_id),
    )
    return count > 0


async def update_plan_fields(
    conn: pymysql.Connection,
    plan_id: int,
    owner_user_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    planner_task_type_id: int | None = None,
    course_id: int | None = None,
    section_id: int | None = None,
    deadline_at: datetime | None = None,
    portal_id: int | None = None,
    grade_component_id: int | None = None,
    priority_id: int | None = None,
    energy_level_id: int | None = None,
    estimated_effort_min: int | None = None,
    clear_course: bool = False,
    clear_section: bool = False,
    clear_energy: bool = False,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if planner_task_type_id is not None:
        fields.append("planner_task_type_id = %s")
        params.append(planner_task_type_id)
    if clear_course:
        fields.append("course_id = NULL")
    elif course_id is not None:
        fields.append("course_id = %s")
        params.append(course_id)
    if clear_section:
        fields.append("section_id = NULL")
    elif section_id is not None:
        fields.append("section_id = %s")
        params.append(section_id)
    if deadline_at is not None:
        fields.append("deadline_at = %s")
        params.append(deadline_at)
    if portal_id is not None:
        fields.append("portal_id = %s")
        params.append(portal_id)
    if grade_component_id is not None:
        fields.append("grade_component_id = %s")
        params.append(grade_component_id)
    if priority_id is not None:
        fields.append("priority_id = %s")
        params.append(priority_id)
    if clear_energy:
        fields.append("energy_level_id = NULL")
    elif energy_level_id is not None:
        fields.append("energy_level_id = %s")
        params.append(energy_level_id)
    if estimated_effort_min is not None:
        fields.append("estimated_effort_min = %s")
        params.append(estimated_effort_min)
    if not fields:
        return True
    params.extend([plan_id, owner_user_id])
    count = await execute(
        conn,
        f"UPDATE planner_event_plans SET {', '.join(fields)} WHERE id = %s AND owner_user_id = %s",
        tuple(params),
    )
    return count > 0


async def propagate_plan_metadata(
    conn: pymysql.Connection,
    plan_id: int,
    user_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    course_id: int | None = None,
    section_id: int | None = None,
    priority_id: int | None = None,
    energy_level_id: int | None = None,
    estimated_effort_min: int | None = None,
    deadline_at: datetime | None = None,
    clear_course: bool = False,
    clear_section: bool = False,
    clear_energy: bool = False,
) -> None:
    task_fields: list[str] = []
    task_params: list[Any] = []
    if title is not None:
        task_fields.append("title = %s")
        task_params.append(title)
    if description is not None:
        task_fields.append("description = %s")
        task_params.append(description)
    if clear_course:
        task_fields.append("course_id = NULL")
    elif course_id is not None:
        task_fields.append("course_id = %s")
        task_params.append(course_id)
    if clear_section:
        task_fields.append("section_id = NULL")
    elif section_id is not None:
        task_fields.append("section_id = %s")
        task_params.append(section_id)
    if priority_id is not None:
        task_fields.append("priority_id = %s")
        task_params.append(priority_id)
    if clear_energy:
        task_fields.append("energy_level_id = NULL")
    elif energy_level_id is not None:
        task_fields.append("energy_level_id = %s")
        task_params.append(energy_level_id)
    if estimated_effort_min is not None:
        task_fields.append("estimated_effort_min = %s")
        task_params.append(estimated_effort_min)
    if deadline_at is not None:
        task_fields.append("due_at = %s")
        task_fields.append("original_due_at = %s")
        task_params.extend([deadline_at, deadline_at])
    if task_fields:
        task_params.extend([plan_id, user_id])
        await execute(
            conn,
            f"""
            UPDATE user_tasks
            SET {', '.join(task_fields)}
            WHERE event_plan_id = %s AND user_id = %s
            """,
            tuple(task_params),
        )

    cal_fields: list[str] = []
    cal_params: list[Any] = []
    if title is not None:
        cal_fields.append("title = %s")
        cal_params.append(title)
    if description is not None:
        cal_fields.append("description = %s")
        cal_params.append(description)
    if clear_course:
        cal_fields.append("course_id = NULL")
    elif course_id is not None:
        cal_fields.append("course_id = %s")
        cal_params.append(course_id)
    if deadline_at is not None:
        cal_fields.append("starts_at = %s")
        cal_fields.append("ends_at = %s")
        cal_params.extend([deadline_at, deadline_at])
    if cal_fields:
        cal_params.extend([plan_id, user_id])
        await execute(
            conn,
            f"""
            UPDATE calendar_events
            SET {', '.join(cal_fields)}
            WHERE event_plan_id = %s AND owner_user_id = %s
            """,
            tuple(cal_params),
        )


async def clear_recurrence(conn: pymysql.Connection, plan_id: int) -> None:
    await execute(conn, "DELETE FROM planner_event_recurrence WHERE plan_id = %s", (plan_id,))


async def skip_all_open_tasks(
    conn: pymysql.Connection, plan_id: int, user_id: int
) -> None:
    await execute(
        conn,
        """
        UPDATE user_tasks
        SET is_skipped = 1, skipped_at = UTC_TIMESTAMP(3)
        WHERE event_plan_id = %s AND user_id = %s AND is_completed = 0 AND is_skipped = 0
        """,
        (plan_id, user_id),
    )


async def delete_calendar_for_plan(
    conn: pymysql.Connection, plan_id: int, owner_user_id: int
) -> None:
    await execute(
        conn,
        "DELETE FROM calendar_events WHERE event_plan_id = %s AND owner_user_id = %s",
        (plan_id, owner_user_id),
    )


async def complete_plan(conn: pymysql.Connection, plan_id: int) -> None:
    await execute(
        conn,
        """
        UPDATE planner_event_plans
        SET is_completed = 1, completed_at = UTC_TIMESTAMP(3), plan_completed_percent = 100
        WHERE id = %s
        """,
        (plan_id,),
    )


async def update_plan_completed_percent(
    conn: pymysql.Connection, plan_id: int, percent: float
) -> None:
    await execute(
        conn,
        "UPDATE planner_event_plans SET plan_completed_percent = %s WHERE id = %s",
        (min(100.0, percent), plan_id),
    )


async def list_recurrence(conn: pymysql.Connection, plan_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT day_of_week, starts_time, duration_min
        FROM planner_event_recurrence WHERE plan_id = %s
        """,
        (plan_id,),
    )


async def sum_completed_portions(
    conn: pymysql.Connection, plan_id: int, before_date: date | None = None
) -> float:
    clauses = ["event_plan_id = %s", "is_skipped = 0"]
    params: list[Any] = [plan_id]
    if before_date is not None:
        clauses.append("slice_date < %s")
        params.append(before_date)
    row = await fetch_one(
        conn,
        f"""
        SELECT COALESCE(SUM(completed_portion_percent), 0) AS total
        FROM user_tasks WHERE {' AND '.join(clauses)}
        """,
        tuple(params),
    )
    return float(row["total"]) if row else 0.0


async def get_yesterday_slice(
    conn: pymysql.Connection, plan_id: int, user_id: int, yesterday: date
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, effective_target_percent, completed_portion_percent, is_skipped, slice_closed
        FROM user_tasks
        WHERE event_plan_id = %s AND user_id = %s AND slice_date = %s
        LIMIT 1
        """,
        (plan_id, user_id, yesterday),
    )


async def count_days_behind(
    conn: pymysql.Connection, plan_id: int, user_id: int, before_date: date
) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COUNT(*) AS n FROM user_tasks
        WHERE event_plan_id = %s AND user_id = %s AND slice_date < %s
          AND is_skipped = 0 AND slice_closed = 1
          AND completed_portion_percent < effective_target_percent
        """,
        (plan_id, user_id, before_date),
    )
    return int(row["n"]) if row else 0


async def close_slice(conn: pymysql.Connection, task_id: int) -> None:
    await execute(
        conn,
        "UPDATE user_tasks SET slice_closed = 1 WHERE id = %s",
        (task_id,),
    )


async def slice_exists(
    conn: pymysql.Connection, plan_id: int, user_id: int, slice_date: date
) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM user_tasks
        WHERE event_plan_id = %s AND user_id = %s AND slice_date = %s
        LIMIT 1
        """,
        (plan_id, user_id, slice_date),
    )
    return row is not None


async def cancel_future_slices(
    conn: pymysql.Connection, plan_id: int, user_id: int, from_date: date
) -> None:
    await execute(
        conn,
        """
        UPDATE user_tasks
        SET is_skipped = 1, skipped_at = UTC_TIMESTAMP(3)
        WHERE event_plan_id = %s AND user_id = %s
          AND slice_date >= %s AND is_completed = 0
        """,
        (plan_id, user_id, from_date),
    )


async def enrolled_count(conn: pymysql.Connection, section_id: int) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COUNT(*) AS n FROM section_enrollments
        WHERE section_id = %s AND dropped_at IS NULL
        """,
        (section_id,),
    )
    return int(row["n"]) if row else 0


async def graded_portal_count(conn: pymysql.Connection, portal_id: int) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COUNT(*) AS n FROM submissions sub
        INNER JOIN submission_statuses ss ON ss.id = sub.status_id
        WHERE sub.portal_id = %s AND ss.code = 'graded'
        """,
        (portal_id,),
    )
    return int(row["n"]) if row else 0


async def graded_component_count(
    conn: pymysql.Connection, section_id: int, component_code: str
) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COUNT(DISTINCT student_user_id) AS n
        FROM section_grades
        WHERE section_id = %s AND component_code = %s
        """,
        (section_id, component_code),
    )
    return int(row["n"]) if row else 0


async def get_component_code(conn: pymysql.Connection, component_id: int) -> str | None:
    row = await fetch_one(
        conn,
        "SELECT component_code FROM section_grade_components WHERE id = %s",
        (component_id,),
    )
    return row["component_code"] if row else None


def iter_recurrence_dates(
    day_of_week: int, weeks: int = 8, start: date | None = None
) -> list[date]:
    """day_of_week: 0=Sunday .. 6=Saturday (matches JS getDay)."""
    start = start or date.today()
    out: list[date] = []
    cur = start
    end = start + timedelta(days=weeks * 7)
    py_dow = (day_of_week + 6) % 7
    while cur <= end:
        if cur.weekday() == py_dow:
            out.append(cur)
        cur += timedelta(days=1)
    return out
