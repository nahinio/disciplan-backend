"""Raw SQL — user tasks and calendar events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def list_tasks(conn: pymysql.Connection, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            ut.id, ut.title, ut.description, ut.due_at, ut.is_completed, ut.completed_at,
            c.code AS course_code,
            tp.code AS priority_code,
            el.code AS energy_level_code,
            at.code AS task_type_code,
            at.label AS task_type_label
        FROM user_tasks ut
        LEFT JOIN courses c ON c.id = ut.course_id
        INNER JOIN task_priorities tp ON tp.id = ut.priority_id
        LEFT JOIN energy_levels el ON el.id = ut.energy_level_id
        LEFT JOIN assessment_types at ON at.id = ut.assessment_type_id
        WHERE ut.user_id = %s
        ORDER BY ut.is_completed ASC, ut.due_at ASC, ut.id ASC
        """,
        (user_id,),
    )


async def create_task(
    conn: pymysql.Connection,
    *,
    user_id: int,
    title: str,
    course_id: int | None,
    priority_code: str,
    due_at: datetime | None,
    energy_level_code: str | None = None,
    description: str | None = None,
    task_type_code: str | None = None,
) -> int:
    priority = await fetch_one(
        conn, "SELECT id FROM task_priorities WHERE code = %s", (priority_code,)
    )
    energy_id = None
    if energy_level_code:
        energy = await fetch_one(
            conn, "SELECT id FROM energy_levels WHERE code = %s", (energy_level_code,)
        )
        energy_id = energy["id"] if energy else None
    assessment_type_id = None
    if task_type_code:
        atype = await fetch_one(
            conn, "SELECT id FROM assessment_types WHERE code = %s", (task_type_code,)
        )
        assessment_type_id = atype["id"] if atype else None
    if not priority:
        raise ValueError("Invalid priority")

    return await execute_returning_id(
        conn,
        """
        INSERT INTO user_tasks (
            user_id, course_id, assessment_type_id, title, description,
            priority_id, energy_level_id, due_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, course_id, assessment_type_id, title, description, priority["id"], energy_id, due_at),
    )


async def update_task(
    conn: pymysql.Connection,
    user_id: int,
    task_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    course_id: int | None = None,
    priority_code: str | None = None,
    energy_level_code: str | None = None,
    task_type_code: str | None = None,
    due_at: datetime | None = None,
    clear_due_at: bool = False,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []

    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if course_id is not None:
        fields.append("course_id = %s")
        params.append(course_id)
    if priority_code is not None:
        priority = await fetch_one(
            conn, "SELECT id FROM task_priorities WHERE code = %s", (priority_code,)
        )
        if priority:
            fields.append("priority_id = %s")
            params.append(priority["id"])
    if energy_level_code is not None:
        energy = await fetch_one(
            conn, "SELECT id FROM energy_levels WHERE code = %s", (energy_level_code,)
        )
        fields.append("energy_level_id = %s")
        params.append(energy["id"] if energy else None)
    if task_type_code is not None:
        atype = await fetch_one(
            conn, "SELECT id FROM assessment_types WHERE code = %s", (task_type_code,)
        )
        fields.append("assessment_type_id = %s")
        params.append(atype["id"] if atype else None)
    if clear_due_at:
        fields.append("due_at = NULL")
    elif due_at is not None:
        fields.append("due_at = %s")
        params.append(due_at)

    if not fields:
        return True

    params.extend([task_id, user_id])
    count = await execute(
        conn,
        f"UPDATE user_tasks SET {', '.join(fields)} WHERE id = %s AND user_id = %s",
        tuple(params),
    )
    return count > 0


async def delete_task(conn: pymysql.Connection, user_id: int, task_id: int) -> bool:
    count = await execute(
        conn, "DELETE FROM user_tasks WHERE id = %s AND user_id = %s", (task_id, user_id)
    )
    return count > 0


async def toggle_task(conn: pymysql.Connection, user_id: int, task_id: int, completed: bool) -> bool:
    count = await execute(
        conn,
        """
        UPDATE user_tasks
        SET is_completed = %s,
            completed_at = CASE WHEN %s = 1 THEN UTC_TIMESTAMP(3) ELSE NULL END
        WHERE id = %s AND user_id = %s
        """,
        (int(completed), int(completed), task_id, user_id),
    )
    return count > 0


async def list_calendar_events(
    conn: pymysql.Connection, user_id: int, *, from_dt: datetime | None = None
) -> list[dict[str, Any]]:
    if from_dt:
        return await fetch_all(
            conn,
            """
            SELECT ce.id, ce.title, ce.description, ce.starts_at, ce.ends_at, ce.all_day,
                   c.code AS course_code
            FROM calendar_events ce
            LEFT JOIN courses c ON c.id = ce.course_id
            WHERE ce.owner_user_id = %s AND ce.ends_at >= %s
            ORDER BY ce.starts_at ASC
            """,
            (user_id, from_dt),
        )
    return await fetch_all(
        conn,
        """
        SELECT ce.id, ce.title, ce.description, ce.starts_at, ce.ends_at, ce.all_day,
               c.code AS course_code
        FROM calendar_events ce
        LEFT JOIN courses c ON c.id = ce.course_id
        WHERE ce.owner_user_id = %s
        ORDER BY ce.starts_at ASC
        LIMIT 100
        """,
        (user_id,),
    )


async def update_calendar_event(
    conn: pymysql.Connection,
    user_id: int,
    event_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    course_id: int | None = None,
    all_day: bool | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if starts_at is not None:
        fields.append("starts_at = %s")
        params.append(starts_at)
    if ends_at is not None:
        fields.append("ends_at = %s")
        params.append(ends_at)
    if course_id is not None:
        fields.append("course_id = %s")
        params.append(course_id)
    if all_day is not None:
        fields.append("all_day = %s")
        params.append(int(all_day))
    if not fields:
        return True
    params.extend([event_id, user_id])
    count = await execute(
        conn,
        f"UPDATE calendar_events SET {', '.join(fields)} WHERE id = %s AND owner_user_id = %s",
        tuple(params),
    )
    return count > 0


async def delete_calendar_event(conn: pymysql.Connection, user_id: int, event_id: int) -> bool:
    count = await execute(
        conn,
        "DELETE FROM calendar_events WHERE id = %s AND owner_user_id = %s",
        (event_id, user_id),
    )
    return count > 0


async def create_calendar_event(
    conn: pymysql.Connection,
    *,
    owner_user_id: int,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    course_id: int | None = None,
    description: str | None = None,
    all_day: bool = False,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO calendar_events (owner_user_id, course_id, title, description, starts_at, ends_at, all_day)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (owner_user_id, course_id, title, description, starts_at, ends_at, int(all_day)),
    )
