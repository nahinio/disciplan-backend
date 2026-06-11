"""Raw SQL — courses, sections, enrollments."""

from __future__ import annotations

from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def list_catalogue(conn: pymysql.Connection) -> list[dict[str, Any]]:
    """All active courses with section count and current semester."""
    return await fetch_all(
        conn,
        """
        SELECT
            c.id,
            c.code,
            c.title,
            c.credit_hours,
            c.has_project,
            ct.code AS course_type_code,
            ct.label AS course_type_label,
            ct.duration_minutes AS class_duration_minutes,
            d.code AS department_code,
            d.name AS department_name,
            COUNT(DISTINCT s.id) AS section_count
        FROM courses c
        INNER JOIN departments d ON d.id = c.department_id
        INNER JOIN course_types ct ON ct.id = c.course_type_id
        LEFT JOIN sections s ON s.course_id = c.id AND s.is_active = 1
        WHERE c.is_active = 1
        GROUP BY c.id, c.code, c.title, c.credit_hours, c.has_project,
                 ct.code, ct.label, ct.duration_minutes, d.code, d.name
        ORDER BY c.code
        """,
    )


async def list_offerings(conn: pymysql.Connection) -> list[dict[str, Any]]:
    """Full routine-style listing with meeting times (complex join + aggregation)."""
    rows = await fetch_all(
        conn,
        """
        SELECT
            c.code AS course_code,
            c.title,
            c.credit_hours AS credit,
            c.has_project,
            ct.code AS course_type_code,
            ct.label AS course_type_label,
            ct.duration_minutes AS class_duration_minutes,
            d.code AS program,
            s.id AS section_id,
            s.section_label AS section,
            s.room,
            sem.label AS semester_label,
            smt.day_id,
            dow.code AS day_code,
            dow.label AS day_label,
            TIME_FORMAT(smt.starts_at, '%%h:%%i %%p') AS starts_label,
            TIME_FORMAT(smt.ends_at, '%%h:%%i %%p') AS ends_label,
            smt.starts_at,
            smt.ends_at
        FROM sections s
        INNER JOIN courses c ON c.id = s.course_id AND c.is_active = 1
        INNER JOIN course_types ct ON ct.id = c.course_type_id
        INNER JOIN departments d ON d.id = c.department_id
        INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
        LEFT JOIN section_meeting_times smt ON smt.section_id = s.id
        LEFT JOIN days_of_week dow ON dow.id = smt.day_id
        WHERE s.is_active = 1
        ORDER BY c.code, s.section_label, smt.day_id, smt.starts_at
        """,
    )

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        sid = row["section_id"]
        if sid not in grouped:
            grouped[sid] = {
                "section_id": sid,
                "course_code": row["course_code"],
                "title": row["title"],
                "credit": float(row["credit"]),
                "has_project": bool(row.get("has_project")),
                "course_type_code": row.get("course_type_code"),
                "course_type_label": row.get("course_type_label"),
                "class_duration_minutes": row.get("class_duration_minutes"),
                "program": row["program"],
                "section": row["section"],
                "room": row["room"],
                "semester_label": row["semester_label"],
                "days": [],
                "times": [],
                "faculty": [],
            }
        if row["day_code"]:
            grouped[sid]["days"].append(row["day_label"])
            grouped[sid]["times"].append(f"{row['starts_label']} - {row['ends_label']}")

    # Attach faculty per section
    faculty_rows = await fetch_all(
        conn,
        """
        SELECT sf.section_id, up.display_name AS faculty_name
        FROM section_faculty sf
        INNER JOIN user_profiles up ON up.user_id = sf.faculty_user_id
        """,
    )
    faculty_map: dict[int, list[str]] = {}
    for f in faculty_rows:
        faculty_map.setdefault(f["section_id"], []).append(f["faculty_name"])
    for sid, item in grouped.items():
        item["faculty"] = faculty_map.get(sid, [])

    return list(grouped.values())


async def get_course_by_code(conn: pymysql.Connection, code: str) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT c.id, c.code, c.title, c.credit_hours, c.has_project,
               ct.code AS course_type_code,
               ct.label AS course_type_label,
               ct.duration_minutes AS class_duration_minutes,
               d.code AS department_code, d.name AS department_name
        FROM courses c
        INNER JOIN departments d ON d.id = c.department_id
        INNER JOIN course_types ct ON ct.id = c.course_type_id
        WHERE c.code = %s AND c.is_active = 1
        """,
        (code,),
    )


async def get_sections_for_course(conn: pymysql.Connection, course_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT s.id, s.section_label, s.room, s.schedule_key, sem.label AS semester_label,
               (SELECT COUNT(*) FROM section_enrollments se
                WHERE se.section_id = s.id AND se.dropped_at IS NULL) AS enrolled_count
        FROM sections s
        INNER JOIN semesters sem ON sem.id = s.semester_id
        WHERE s.course_id = %s AND s.is_active = 1
        ORDER BY s.section_label
        """,
        (course_id,),
    )


async def find_section(conn: pymysql.Connection, course_code: str, section_label: str) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT s.id, s.section_label, s.course_id, c.code AS course_code, c.title
        FROM sections s
        INNER JOIN courses c ON c.id = s.course_id
        INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
        WHERE c.code = %s AND s.section_label = %s AND s.is_active = 1
        """,
        (course_code, section_label),
    )


async def enroll_student(conn: pymysql.Connection, section_id: int, student_user_id: int) -> None:
    existing = await fetch_one(
        conn,
        """
        SELECT id FROM section_enrollments
        WHERE section_id = %s AND student_user_id = %s AND dropped_at IS NULL
        """,
        (section_id, student_user_id),
    )
    if existing:
        return
    await execute(
        conn,
        """
        INSERT INTO section_enrollments (section_id, student_user_id)
        VALUES (%s, %s)
        """,
        (section_id, student_user_id),
    )


async def assign_faculty(conn: pymysql.Connection, section_id: int, faculty_user_id: int) -> None:
    await execute(
        conn,
        """
        INSERT IGNORE INTO section_faculty (section_id, faculty_user_id)
        VALUES (%s, %s)
        """,
        (section_id, faculty_user_id),
    )


async def list_accessible_course_ids(
    conn: pymysql.Connection, user_id: int, role_code: str
) -> list[int]:
    if role_code == "admin":
        rows = await fetch_all(conn, "SELECT id FROM courses ORDER BY code")
        return [int(r["id"]) for r in rows]

    sections = await list_user_sections(conn, user_id, role_code)
    if not sections:
        return []

    codes = list({str(s["course_code"]) for s in sections})
    placeholders = ", ".join(["%s"] * len(codes))
    rows = await fetch_all(
        conn,
        f"SELECT id FROM courses WHERE code IN ({placeholders})",
        tuple(codes),
    )
    return [int(r["id"]) for r in rows]


async def user_has_course_access(
    conn: pymysql.Connection, user_id: int, role_code: str, course_id: int
) -> bool:
    if role_code == "admin":
        return True
    accessible = await list_accessible_course_ids(conn, user_id, role_code)
    return course_id in accessible


async def list_user_sections(conn: pymysql.Connection, user_id: int, role_code: str) -> list[dict[str, Any]]:
    if role_code == "faculty":
        return await fetch_all(
            conn,
            """
            SELECT s.id AS section_id, c.code AS course_code, c.title, s.section_label,
                   CONCAT(c.code, '::', s.section_label) AS section_key
            FROM section_faculty sf
            INNER JOIN sections s ON s.id = sf.section_id AND s.is_active = 1
            INNER JOIN courses c ON c.id = s.course_id
            WHERE sf.faculty_user_id = %s
            ORDER BY c.code, s.section_label
            """,
            (user_id,),
        )

    return await fetch_all(
        conn,
        """
        SELECT s.id AS section_id, c.code AS course_code, c.title, s.section_label,
               CONCAT(c.code, '::', s.section_label) AS section_key
        FROM section_enrollments se
        INNER JOIN sections s ON s.id = se.section_id AND s.is_active = 1
        INNER JOIN courses c ON c.id = s.course_id
        WHERE se.student_user_id = %s AND se.dropped_at IS NULL
        ORDER BY c.code, s.section_label
        """,
        (user_id,),
    )


async def get_syllabus_topics(conn: pymysql.Connection, course_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT id, title, week_number, sort_order
        FROM syllabus_topics
        WHERE course_id = %s
        ORDER BY sort_order, week_number
        """,
        (course_id,),
    )


async def update_profile(
    conn: pymysql.Connection,
    user_id: int,
    *,
    display_name: str | None = None,
    department_id: int | None = None,
    avatar_file_id: int | None = ...,
    avatar_preset: str | None = ...,
) -> None:
    existing = await fetch_one(
        conn,
        "SELECT display_name, department_id FROM user_profiles WHERE user_id = %s",
        (user_id,),
    )
    name = display_name if display_name is not None else (existing["display_name"] if existing else "User")
    dept = department_id if department_id is not None else (existing["department_id"] if existing else None)

    await execute(
        conn,
        """
        INSERT INTO user_profiles (user_id, display_name, department_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            display_name = VALUES(display_name),
            department_id = VALUES(department_id)
        """,
        (user_id, name, dept),
    )

    fields: list[str] = []
    params: list[Any] = []
    if avatar_file_id is not ...:
        fields.append("avatar_file_id = %s")
        params.append(avatar_file_id)
        fields.append("avatar_preset = NULL")
    elif avatar_preset is not ...:
        fields.append("avatar_preset = %s")
        params.append(avatar_preset)
        fields.append("avatar_file_id = NULL")
    if fields:
        params.append(user_id)
        await execute(
            conn,
            f"UPDATE user_profiles SET {', '.join(fields)} WHERE user_id = %s",
            tuple(params),
        )


async def drop_student(conn: pymysql.Connection, section_id: int, student_user_id: int) -> bool:
    count = await execute(
        conn,
        """
        UPDATE section_enrollments
        SET dropped_at = UTC_TIMESTAMP(3)
        WHERE section_id = %s AND student_user_id = %s AND dropped_at IS NULL
        """,
        (section_id, student_user_id),
    )
    return count > 0
