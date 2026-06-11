"""Raw SQL — admin console: users, courses, announcements, audit."""

from __future__ import annotations

import json
import re
from typing import Any

import pymysql

from datetime import datetime, timezone

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def log_action(
    conn: pymysql.Connection,
    *,
    actor_user_id: int | None,
    action_code: str,
    entity_type_code: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> int:
    action = await fetch_one(
        conn, "SELECT id FROM audit_action_types WHERE code = %s", (action_code,)
    )
    if not action:
        raise ValueError(f"Unknown audit action: {action_code}")

    entity_type_id = None
    if entity_type_code:
        et = await fetch_one(
            conn, "SELECT id FROM reference_entity_types WHERE code = %s", (entity_type_code,)
        )
        entity_type_id = et["id"] if et else None

    return await execute_returning_id(
        conn,
        """
        INSERT INTO audit_logs (
            actor_user_id, action_type_id, entity_type_id, entity_id, details_json, ip_address
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            actor_user_id,
            action["id"],
            entity_type_id,
            entity_id,
            json.dumps(details) if details else None,
            ip_address,
        ),
    )


async def list_users(conn: pymysql.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            u.id, u.email, u.email_verified, u.created_at,
            r.code AS role_code,
            us.code AS status_code,
            up.display_name AS name,
            d.code AS department_code, d.name AS department_name
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_statuses us ON us.id = u.status_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN departments d ON d.id = up.department_id
        ORDER BY u.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


async def update_user(
    conn: pymysql.Connection,
    user_id: int,
    *,
    role_code: str | None = None,
    status_code: str | None = None,
    display_name: str | None = None,
    department_id: int | None = None,
) -> None:
    if role_code:
        role = await fetch_one(conn, "SELECT id FROM roles WHERE code = %s", (role_code,))
        if role:
            await execute(conn, "UPDATE users SET role_id = %s WHERE id = %s", (role["id"], user_id))
    if status_code:
        status = await fetch_one(conn, "SELECT id FROM user_statuses WHERE code = %s", (status_code,))
        if status:
            await execute(conn, "UPDATE users SET status_id = %s WHERE id = %s", (status["id"], user_id))
    if display_name is not None or department_id is not None:
        await execute(
            conn,
            """
            INSERT INTO user_profiles (user_id, display_name, department_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                display_name = COALESCE(VALUES(display_name), display_name),
                department_id = COALESCE(VALUES(department_id), department_id)
            """,
            (user_id, display_name or "User", department_id),
        )


def _derive_department_code(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name.strip())
    if not words:
        return "DEPT"
    if len(words) == 1:
        return words[0].upper()[:20]
    acronym = "".join(w[0].upper() for w in words if w)
    return acronym[:20] if acronym else "DEPT"


async def get_department_by_id(
    conn: pymysql.Connection, department_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        "SELECT id, code, name FROM departments WHERE id = %s",
        (department_id,),
    )


async def update_department(
    conn: pymysql.Connection,
    department_id: int,
    *,
    name: str,
) -> dict[str, Any] | None:
    dept = await get_department_by_id(conn, department_id)
    if not dept:
        return None
    clean_name = name.strip()
    await execute(
        conn,
        "UPDATE departments SET name = %s WHERE id = %s",
        (clean_name, department_id),
    )
    return {"id": department_id, "code": dept["code"], "name": clean_name}


async def _delete_section_ids(
    conn: pymysql.Connection, section_ids: list[int]
) -> None:
    if not section_ids:
        return
    s_ph = ",".join(["%s"] * len(section_ids))
    params = tuple(section_ids)

    await execute(
        conn,
        f"""
        DELETE sac FROM section_announcement_comments sac
        INNER JOIN section_announcements sa ON sa.id = sac.announcement_id
        WHERE sa.section_id IN ({s_ph})
        """,
        params,
    )
    await execute(
        conn,
        f"""
        DELETE sf FROM submission_files sf
        INNER JOIN submissions sub ON sub.id = sf.submission_id
        INNER JOIN assessment_portals ap ON ap.id = sub.portal_id
        WHERE ap.section_id IN ({s_ph})
        """,
        params,
    )
    await execute(
        conn,
        f"""
        DELETE sub FROM submissions sub
        INNER JOIN assessment_portals ap ON ap.id = sub.portal_id
        WHERE ap.section_id IN ({s_ph})
        """,
        params,
    )
    await execute(
        conn,
        f"DELETE FROM assessment_portals WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_grade_components WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_grades WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_enrollments WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_doubts WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_announcements WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_resources WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM user_lecture_task_log WHERE section_id IN ({s_ph})",
        params,
    )

    chat_groups = await fetch_all(
        conn,
        f"SELECT id FROM chat_groups WHERE section_id IN ({s_ph})",
        params,
    )
    if chat_groups:
        g_ids = tuple(g["id"] for g in chat_groups)
        g_ph = ",".join(["%s"] * len(g_ids))
        await execute(
            conn,
            f"DELETE FROM chat_messages WHERE group_id IN ({g_ph})",
            g_ids,
        )
        await execute(
            conn,
            f"DELETE FROM chat_groups WHERE id IN ({g_ph})",
            g_ids,
        )

    await execute(
        conn,
        f"DELETE FROM teams WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_meeting_times WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM section_faculty WHERE section_id IN ({s_ph})",
        params,
    )
    await execute(conn, f"DELETE FROM sections WHERE id IN ({s_ph})", params)


async def _delete_sections_for_courses(
    conn: pymysql.Connection, course_ids: list[int]
) -> None:
    if not course_ids:
        return
    placeholders = ",".join(["%s"] * len(course_ids))
    sections = await fetch_all(
        conn,
        f"SELECT id FROM sections WHERE course_id IN ({placeholders})",
        tuple(course_ids),
    )
    section_ids = [s["id"] for s in sections]
    await _delete_section_ids(conn, section_ids)


async def _delete_courses_cascade(
    conn: pymysql.Connection, course_ids: list[int]
) -> None:
    if not course_ids:
        return
    placeholders = ",".join(["%s"] * len(course_ids))
    params = tuple(course_ids)

    await _delete_sections_for_courses(conn, course_ids)
    await execute(
        conn,
        f"DELETE FROM teams WHERE course_id IN ({placeholders})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM blog_posts WHERE course_id IN ({placeholders})",
        params,
    )
    await execute(
        conn,
        f"DELETE FROM forum_threads WHERE course_id IN ({placeholders})",
        params,
    )
    await execute(conn, f"DELETE FROM courses WHERE id IN ({placeholders})", params)


async def delete_department(
    conn: pymysql.Connection, department_id: int
) -> dict[str, Any] | None:
    dept = await get_department_by_id(conn, department_id)
    if not dept:
        return None

    courses = await fetch_all(
        conn,
        "SELECT id FROM courses WHERE department_id = %s",
        (department_id,),
    )
    course_ids = [c["id"] for c in courses]
    if course_ids:
        await _delete_courses_cascade(conn, course_ids)

    await execute(
        conn,
        "UPDATE user_profiles SET department_id = NULL WHERE department_id = %s",
        (department_id,),
    )
    await execute(conn, "DELETE FROM departments WHERE id = %s", (department_id,))

    return {
        "id": department_id,
        "code": dept["code"],
        "name": dept["name"],
        "courses_deleted": len(course_ids),
    }


async def create_department(
    conn: pymysql.Connection,
    *,
    name: str,
    code: str | None = None,
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Department name is required")

    explicit_code = code.strip().upper()[:20] if code and code.strip() else None
    base_code = explicit_code or _derive_department_code(clean_name).upper()[:20]

    if explicit_code:
        if await fetch_one(conn, "SELECT id FROM departments WHERE code = %s", (base_code,)):
            raise ValueError(f"Department code '{base_code}' already exists")
        final_code = base_code
    else:
        final_code = base_code
        suffix = 1
        while await fetch_one(
            conn, "SELECT id FROM departments WHERE code = %s", (final_code,)
        ):
            suffix += 1
            final_code = f"{base_code[:17]}{suffix}"[:20]

    dept_id = await execute_returning_id(
        conn,
        "INSERT INTO departments (code, name) VALUES (%s, %s)",
        (final_code, clean_name),
    )
    return {"id": dept_id, "code": final_code, "name": clean_name}


async def _course_type_id(conn: pymysql.Connection, course_type_code: str) -> int:
    row = await fetch_one(
        conn, "SELECT id FROM course_types WHERE code = %s LIMIT 1", (course_type_code,)
    )
    if not row:
        raise ValueError(f"Unknown course type: {course_type_code}")
    return int(row["id"])


async def create_course(
    conn: pymysql.Connection,
    *,
    code: str,
    title: str,
    department_id: int,
    credit_hours: float,
    has_project: bool,
    course_type_code: str = "theory",
) -> int:
    course_type_id = await _course_type_id(conn, course_type_code)
    return await execute_returning_id(
        conn,
        """
        INSERT INTO courses (
            code, title, department_id, credit_hours, course_type_id, has_project, is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, 1)
        """,
        (code, title, department_id, credit_hours, course_type_id, int(has_project)),
    )


async def list_sections(conn: pymysql.Connection) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            s.id AS section_id,
            c.code AS course_code,
            c.title AS course_title,
            s.section_label AS section,
            s.room,
            s.schedule_key,
            sem.label AS semester_label,
            ct.code AS course_type_code,
            ct.label AS course_type_label,
            ct.duration_minutes AS class_duration_minutes,
            (
                SELECT GROUP_CONCAT(dow.label ORDER BY dow.sort_order SEPARATOR ', ')
                FROM section_meeting_times smt
                INNER JOIN days_of_week dow ON dow.id = smt.day_id
                WHERE smt.section_id = s.id
            ) AS schedule_days,
            (
                SELECT TIME_FORMAT(MIN(smt.starts_at), '%%H:%%i')
                FROM section_meeting_times smt
                WHERE smt.section_id = s.id
            ) AS starts_at,
            (
                SELECT TIME_FORMAT(MIN(smt.ends_at), '%%H:%%i')
                FROM section_meeting_times smt
                WHERE smt.section_id = s.id
            ) AS ends_at,
            GROUP_CONCAT(DISTINCT up.display_name ORDER BY up.display_name SEPARATOR ', ') AS faculty_name,
            MIN(sf.faculty_user_id) AS faculty_user_id
        FROM sections s
        INNER JOIN courses c ON c.id = s.course_id AND c.is_active = 1
        INNER JOIN course_types ct ON ct.id = c.course_type_id
        INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
        LEFT JOIN section_faculty sf ON sf.section_id = s.id
        LEFT JOIN user_profiles up ON up.user_id = sf.faculty_user_id
        WHERE s.is_active = 1
        GROUP BY s.id, c.code, c.title, s.section_label, s.room, s.schedule_key, sem.label,
                 ct.code, ct.label, ct.duration_minutes
        ORDER BY c.code, s.section_label
        """,
    )


async def set_section_faculty(
    conn: pymysql.Connection, section_id: int, faculty_user_id: int | None
) -> None:
    await execute(conn, "DELETE FROM section_faculty WHERE section_id = %s", (section_id,))
    if faculty_user_id is not None:
        faculty = await fetch_one(
            conn,
            """
            SELECT u.id
            FROM users u
            INNER JOIN roles r ON r.id = u.role_id
            WHERE u.id = %s AND r.code = 'faculty'
            """,
            (faculty_user_id,),
        )
        if not faculty:
            raise ValueError("Faculty user not found")
        await execute(
            conn,
            "INSERT INTO section_faculty (section_id, faculty_user_id) VALUES (%s, %s)",
            (section_id, faculty_user_id),
        )


async def set_section_schedule(
    conn: pymysql.Connection,
    *,
    section_id: int,
    course_id: int,
    schedule_key: str,
    starts_at: str,
) -> None:
    from app.services.course_schedule import (
        add_minutes_to_time,
        day_ids_for_schedule,
        normalize_time_value,
    )

    course_row = await fetch_one(
        conn,
        """
        SELECT ct.code AS course_type_code, ct.duration_minutes
        FROM courses c
        INNER JOIN course_types ct ON ct.id = c.course_type_id
        WHERE c.id = %s
        """,
        (course_id,),
    )
    if not course_row:
        raise ValueError("Course not found")
    course_type_code = str(course_row["course_type_code"])
    duration = int(course_row["duration_minutes"])
    day_ids = day_ids_for_schedule(course_type_code, schedule_key)
    start_norm = normalize_time_value(starts_at)
    end_norm = add_minutes_to_time(start_norm, duration)

    await execute(
        conn,
        "UPDATE sections SET schedule_key = %s WHERE id = %s",
        (schedule_key.lower(), section_id),
    )
    await execute(
        conn, "DELETE FROM section_meeting_times WHERE section_id = %s", (section_id,)
    )
    for day_id in day_ids:
        await execute_returning_id(
            conn,
            """
            INSERT INTO section_meeting_times (section_id, day_id, starts_at, ends_at)
            VALUES (%s, %s, %s, %s)
            """,
            (section_id, day_id, start_norm, end_norm),
        )


async def create_section(
    conn: pymysql.Connection,
    *,
    course_id: int,
    section_label: str,
    room: str | None,
    faculty_user_id: int | None = None,
    schedule_key: str | None = None,
    starts_at: str | None = None,
) -> int:
    sem = await fetch_one(conn, "SELECT id FROM semesters WHERE is_current = 1 LIMIT 1")
    if not sem:
        raise ValueError("No current semester configured")
    section_id = await execute_returning_id(
        conn,
        """
        INSERT INTO sections (course_id, semester_id, section_label, room, is_active)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (course_id, sem["id"], section_label, room),
    )
    if faculty_user_id is not None:
        await set_section_faculty(conn, section_id, faculty_user_id)
    if (schedule_key is None) != (starts_at is None):
        raise ValueError("schedule_key and starts_at must be provided together")
    if schedule_key is not None and starts_at is not None:
        await set_section_schedule(
            conn,
            section_id=section_id,
            course_id=course_id,
            schedule_key=schedule_key,
            starts_at=starts_at,
        )
    return section_id


async def list_global_announcements(conn: pymysql.Connection) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            ga.id, ga.title, ga.body AS content, ga.is_active AS active,
            ga.scheduled_for, ga.created_at,
            up.display_name AS author_name,
            GROUP_CONCAT(r.code ORDER BY r.code) AS target_audiences
        FROM global_announcements ga
        INNER JOIN user_profiles up ON up.user_id = ga.author_user_id
        LEFT JOIN global_announcement_audiences gaa ON gaa.announcement_id = ga.id
        LEFT JOIN roles r ON r.id = gaa.role_id
        GROUP BY ga.id, ga.title, ga.body, ga.is_active, ga.scheduled_for, ga.created_at, up.display_name
        ORDER BY ga.created_at DESC
        """,
    )


async def create_global_announcement(
    conn: pymysql.Connection,
    *,
    author_user_id: int,
    title: str,
    body: str,
    is_active: bool,
    scheduled_for: str | None,
    target_audience: str,
) -> int:
    ann_id = await execute_returning_id(
        conn,
        """
        INSERT INTO global_announcements (author_user_id, title, body, is_active, scheduled_for)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (author_user_id, title, body, int(is_active), scheduled_for),
    )

    if target_audience == "all":
        roles = await fetch_all(
            conn, "SELECT id FROM roles WHERE code IN ('student', 'faculty')"
        )
    else:
        roles = await fetch_all(conn, "SELECT id FROM roles WHERE code = %s", (target_audience,))

    for role in roles:
        await execute(
            conn,
            "INSERT INTO global_announcement_audiences (announcement_id, role_id) VALUES (%s, %s)",
            (ann_id, role["id"]),
        )

    if _global_announcement_should_notify(is_active, scheduled_for):
        await _notify_global_announcement(
            conn,
            announcement_id=ann_id,
            author_user_id=author_user_id,
            title=title,
            body=body,
        )
    return ann_id


def _global_announcement_should_notify(is_active: bool, scheduled_for: str | None) -> bool:
    if not is_active:
        return False
    if not scheduled_for:
        return True
    try:
        normalized = scheduled_for.replace("Z", "+00:00")
        sched = datetime.fromisoformat(normalized)
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)
        return sched <= datetime.now(timezone.utc)
    except ValueError:
        return True


async def _notify_global_announcement(
    conn: pymysql.Connection,
    *,
    announcement_id: int,
    author_user_id: int,
    title: str,
    body: str,
) -> None:
    await execute(
        conn,
        """
        INSERT INTO notifications (
            recipient_user_id, type_id, title, body_preview,
            reference_type_id, reference_id, action_path
        )
        SELECT
            u.id,
            (SELECT id FROM notification_types WHERE code = 'system' LIMIT 1),
            %s,
            LEFT(%s, 300),
            (SELECT id FROM reference_entity_types WHERE code = 'announcement' LIMIT 1),
            %s,
            '/notifications'
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_statuses us ON us.id = u.status_id
        INNER JOIN global_announcement_audiences gaa
            ON gaa.role_id = r.id AND gaa.announcement_id = %s
        WHERE us.code = 'active' AND u.id <> %s
        """,
        (
            f"System announcement: {title}",
            body,
            announcement_id,
            announcement_id,
            author_user_id,
        ),
    )


async def list_active_global_announcements(
    conn: pymysql.Connection, role_code: str
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            ga.id, ga.title, ga.body AS content, ga.scheduled_for, ga.created_at,
            up.display_name AS author_name
        FROM global_announcements ga
        INNER JOIN user_profiles up ON up.user_id = ga.author_user_id
        WHERE ga.is_active = 1
          AND (ga.scheduled_for IS NULL OR ga.scheduled_for <= UTC_TIMESTAMP(3))
          AND (
            NOT EXISTS (
                SELECT 1 FROM global_announcement_audiences gaa WHERE gaa.announcement_id = ga.id
            )
            OR EXISTS (
                SELECT 1 FROM global_announcement_audiences gaa
                INNER JOIN roles r ON r.id = gaa.role_id
                WHERE gaa.announcement_id = ga.id AND r.code = %s
            )
          )
        ORDER BY ga.created_at DESC
        LIMIT 50
        """,
        (role_code,),
    )


async def update_course(
    conn: pymysql.Connection,
    course_id: int,
    *,
    title: str | None = None,
    is_active: bool | None = None,
    has_project: bool | None = None,
    course_type_code: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if is_active is not None:
        fields.append("is_active = %s")
        params.append(int(is_active))
    if has_project is not None:
        fields.append("has_project = %s")
        params.append(int(has_project))
    if course_type_code is not None:
        fields.append("course_type_id = %s")
        params.append(await _course_type_id(conn, course_type_code))
    if not fields:
        return True
    params.append(course_id)
    count = await execute(
        conn, f"UPDATE courses SET {', '.join(fields)} WHERE id = %s", tuple(params)
    )
    return count > 0


async def activity_summary(conn: pymysql.Connection) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS total_users,
            (SELECT COUNT(*) FROM courses WHERE is_active = 1) AS active_courses,
            (SELECT COUNT(*) FROM blog_posts WHERE deleted_at IS NULL) AS blog_posts,
            (SELECT COUNT(*) FROM forum_threads WHERE deleted_at IS NULL) AS forum_threads,
            (SELECT COUNT(*) FROM submissions) AS submissions,
            (SELECT COUNT(*) FROM teams WHERE disbanded_at IS NULL) AS active_teams
        """,
    )
    top_courses = await fetch_all(
        conn,
        """
        SELECT c.code, c.title, COUNT(se.id) AS enrollments
        FROM courses c
        LEFT JOIN sections s ON s.course_id = c.id
        LEFT JOIN section_enrollments se ON se.section_id = s.id AND se.dropped_at IS NULL
        WHERE c.is_active = 1
        GROUP BY c.id, c.code, c.title
        ORDER BY enrollments DESC
        LIMIT 5
        """,
    )
    return {"summary": row or {}, "top_courses": top_courses}


async def catalog_content_stats(conn: pymysql.Connection) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            c.id,
            c.code,
            c.title,
            d.code AS department_code,
            d.name AS department_name,
            (
                SELECT COUNT(*)
                FROM syllabus_topics st
                WHERE st.course_id = c.id
            ) AS topic_count,
            (
                SELECT COUNT(*)
                FROM blog_posts bp
                WHERE bp.course_id = c.id AND bp.deleted_at IS NULL
            ) AS blog_count,
            (
                SELECT COUNT(*)
                FROM practice_problems pp
                INNER JOIN syllabus_topics st ON st.id = pp.topic_id
                WHERE st.course_id = c.id
            ) AS problem_count
        FROM courses c
        LEFT JOIN departments d ON d.id = c.department_id
        WHERE c.is_active = 1
        ORDER BY c.code ASC
        """,
    )


async def update_global_announcement(
    conn: pymysql.Connection,
    announcement_id: int,
    *,
    title: str | None = None,
    body: str | None = None,
    is_active: bool | None = None,
    scheduled_for: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if body is not None:
        fields.append("body = %s")
        params.append(body)
    if is_active is not None:
        fields.append("is_active = %s")
        params.append(int(is_active))
    if scheduled_for is not None:
        fields.append("scheduled_for = %s")
        params.append(scheduled_for)
    if not fields:
        return True
    params.append(announcement_id)
    count = await execute(
        conn,
        f"UPDATE global_announcements SET {', '.join(fields)} WHERE id = %s",
        tuple(params),
    )
    return count > 0


async def delete_global_announcement(conn: pymysql.Connection, announcement_id: int) -> bool:
    count = await execute(
        conn, "DELETE FROM global_announcements WHERE id = %s", (announcement_id,)
    )
    return count > 0


async def update_section(
    conn: pymysql.Connection,
    section_id: int,
    *,
    room: str | None = None,
    faculty_user_id: int | None = ...,
    schedule_key: str | None = None,
    starts_at: str | None = None,
) -> bool:
    section = await fetch_one(
        conn,
        "SELECT id, course_id FROM sections WHERE id = %s AND is_active = 1",
        (section_id,),
    )
    if not section:
        return False

    if room is not None:
        await execute(
            conn,
            "UPDATE sections SET room = %s WHERE id = %s",
            (room or None, section_id),
        )
    if faculty_user_id is not ...:
        await set_section_faculty(conn, section_id, faculty_user_id)
    if schedule_key is not None or starts_at is not None:
        if schedule_key is None or starts_at is None:
            raise ValueError("schedule_key and starts_at must be provided together")
        await set_section_schedule(
            conn,
            section_id=section_id,
            course_id=int(section["course_id"]),
            schedule_key=schedule_key,
            starts_at=starts_at,
        )
    return True


async def get_user_admin(conn: pymysql.Connection, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT u.id, u.email, r.code AS role_code, us.code AS status_code,
               up.display_name AS name
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_statuses us ON us.id = u.status_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.id = %s
        """,
        (user_id,),
    )

async def _purge_user_references(conn: pymysql.Connection, user_id: int, email: str) -> None:
    """Remove rows that block deleting a user (non-CASCADE FKs)."""
    uid = user_id

    await execute(conn, "DELETE FROM refresh_tokens WHERE user_id = %s", (uid,))
    await execute(
        conn,
        "UPDATE content_reports SET resolved_by_user_id = NULL WHERE resolved_by_user_id = %s",
        (uid,),
    )
    await execute(conn, "DELETE FROM content_reports WHERE reporter_user_id = %s", (uid,))

    await execute(conn, "DELETE FROM chat_messages WHERE sender_user_id = %s", (uid,))

    await execute(conn, "DELETE FROM blog_comments WHERE author_user_id = %s", (uid,))
    posts = await fetch_all(conn, "SELECT id FROM blog_posts WHERE author_user_id = %s", (uid,))
    for post in posts:
        await execute(conn, "DELETE FROM blog_posts WHERE id = %s", (post["id"],))

    await execute(conn, "DELETE FROM forum_replies WHERE author_user_id = %s", (uid,))
    threads = await fetch_all(conn, "SELECT id FROM forum_threads WHERE author_user_id = %s", (uid,))
    for thread in threads:
        await execute(conn, "DELETE FROM forum_threads WHERE id = %s", (thread["id"],))

    await execute(conn, "DELETE FROM section_doubt_answers WHERE author_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM section_doubts WHERE author_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM section_enrollments WHERE student_user_id = %s", (uid,))

    await execute(
        conn,
        """
        DELETE sf FROM submission_files sf
        INNER JOIN submissions sub ON sub.id = sf.submission_id
        WHERE sub.student_user_id = %s
        """,
        (uid,),
    )
    await execute(conn, "DELETE FROM submissions WHERE student_user_id = %s", (uid,))
    await execute(
        conn, "UPDATE submissions SET graded_by_user_id = NULL WHERE graded_by_user_id = %s", (uid,)
    )

    await execute(
        conn,
        "DELETE FROM section_grades WHERE student_user_id = %s OR recorded_by_user_id = %s",
        (uid, uid),
    )

    await execute(
        conn,
        """
        DELETE sac FROM section_announcement_comments sac
        WHERE sac.author_user_id = %s
        """,
        (uid,),
    )
    await execute(conn, "DELETE FROM section_announcements WHERE author_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM section_resources WHERE created_by_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM section_grade_components WHERE created_by_user_id = %s", (uid,))

    portals = await fetch_all(
        conn, "SELECT id FROM assessment_portals WHERE created_by_user_id = %s", (uid,)
    )
    for portal in portals:
        pid = portal["id"]
        await execute(
            conn,
            """
            DELETE sf FROM submission_files sf
            INNER JOIN submissions sub ON sub.id = sf.submission_id
            WHERE sub.portal_id = %s
            """,
            (pid,),
        )
        await execute(conn, "DELETE FROM submissions WHERE portal_id = %s", (pid,))
        await execute(conn, "DELETE FROM assessment_portals WHERE id = %s", (pid,))

    await execute(conn, "DELETE FROM team_invitations WHERE invited_by_user_id = %s", (uid,))
    teams = await fetch_all(conn, "SELECT id FROM teams WHERE created_by_user_id = %s", (uid,))
    for team in teams:
        await execute(conn, "DELETE FROM teams WHERE id = %s", (team["id"],))

    await execute(conn, "DELETE FROM team_announcements WHERE author_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM team_tasks WHERE created_by_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM team_important_dates WHERE created_by_user_id = %s", (uid,))

    await execute(
        conn,
        "UPDATE blog_posts SET verified_by_user_id = NULL WHERE verified_by_user_id = %s",
        (uid,),
    )
    await execute(
        conn,
        "UPDATE section_doubts SET verified_by_user_id = NULL WHERE verified_by_user_id = %s",
        (uid,),
    )

    await execute(conn, "DELETE FROM past_papers WHERE uploaded_by_user_id = %s", (uid,))
    await execute(conn, "DELETE FROM practice_problems WHERE created_by_user_id = %s", (uid,))

    await execute(conn, "DELETE FROM faculty_roster WHERE claimed_user_id = %s OR LOWER(email) = LOWER(%s)", (uid, email))
    await execute(conn, "DELETE FROM faculty_verification_requests WHERE user_id = %s", (uid,))
    await execute(conn, "DELETE FROM section_enrollment_requests WHERE student_user_id = %s", (uid,))

    file_rows = await fetch_all(conn, "SELECT id FROM files WHERE uploaded_by_user_id = %s", (uid,))
    for frow in file_rows:
        fid = frow["id"]
        await execute(conn, "DELETE FROM chat_message_attachments WHERE file_id = %s", (fid,))
        await execute(conn, "DELETE FROM forum_thread_attachments WHERE file_id = %s", (fid,))
        await execute(conn, "DELETE FROM submission_files WHERE file_id = %s", (fid,))
        await execute(conn, "DELETE FROM files WHERE id = %s", (fid,))


async def delete_user(
    conn: pymysql.Connection,
    user_id: int,
    *,
    delete_faculty_sections: bool = False,
) -> dict[str, Any] | None:
    user = await get_user_admin(conn, user_id)
    if not user:
        return None

    if delete_faculty_sections and user["role_code"] == "faculty":
        section_rows = await fetch_all(
            conn,
            "SELECT DISTINCT section_id FROM section_faculty WHERE faculty_user_id = %s",
            (user_id,),
        )
        for row in section_rows:
            await delete_section(conn, int(row["section_id"]))

    await _purge_user_references(conn, user_id, user["email"])
    await execute(conn, "DELETE FROM users WHERE id = %s", (user_id,))
    return user


async def delete_section(conn: pymysql.Connection, section_id: int) -> bool:
    section = await fetch_one(
        conn, "SELECT id FROM sections WHERE id = %s", (section_id,)
    )
    if not section:
        return False
    await _delete_section_ids(conn, [section_id])
    return True


async def list_audit_logs(conn: pymysql.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            al.id, al.created_at AS timestamp,
            aat.code AS action, aat.label AS action_label,
            ret.code AS entity_type,
            al.entity_id, al.details_json AS details,
            up.display_name AS user_name,
            u.email AS user_email
        FROM audit_logs al
        INNER JOIN audit_action_types aat ON aat.id = al.action_type_id
        LEFT JOIN reference_entity_types ret ON ret.id = al.entity_type_id
        LEFT JOIN users u ON u.id = al.actor_user_id
        LEFT JOIN user_profiles up ON up.user_id = al.actor_user_id
        ORDER BY al.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
