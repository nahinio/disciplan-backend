"""Section enrollment requests and admin enrollment management."""

from __future__ import annotations

import csv
import io
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one
from app.repositories import academic_repo, chat_repo


_REQUEST_LIST_SQL = """
    SELECT
        ser.id,
        ser.student_user_id,
        ser.section_id,
        ser.status,
        ser.message,
        ser.created_at,
        ser.reviewed_at,
        u.email AS student_email,
        up.display_name AS student_name,
        c.code AS course_code,
        c.title AS course_title,
        s.section_label,
        rev.display_name AS reviewed_by_name
    FROM section_enrollment_requests ser
    INNER JOIN users u ON u.id = ser.student_user_id
    LEFT JOIN user_profiles up ON up.user_id = ser.student_user_id
    INNER JOIN sections s ON s.id = ser.section_id
    INNER JOIN courses c ON c.id = s.course_id
    LEFT JOIN user_profiles rev ON rev.user_id = ser.reviewed_by_user_id
"""


async def link_student_to_section(
    conn: pymysql.Connection,
    *,
    section: dict[str, Any],
    student_user_id: int,
    created_by_user_id: int,
) -> None:
    await academic_repo.enroll_student(conn, section["id"], student_user_id)
    await chat_repo.ensure_section_chat_member(
        conn,
        section_id=section["id"],
        user_id=student_user_id,
        group_name=f"{section['course_code']} {section['section_label']} Chat",
        created_by_user_id=created_by_user_id,
    )


async def _student_already_enrolled(
    conn: pymysql.Connection, section_id: int, student_user_id: int
) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM section_enrollments
        WHERE section_id = %s AND student_user_id = %s AND dropped_at IS NULL
        """,
        (section_id, student_user_id),
    )
    return row is not None


async def create_request(
    conn: pymysql.Connection,
    *,
    student_user_id: int,
    course_code: str,
    section_label: str,
    message: str | None = None,
) -> int:
    section = await academic_repo.find_section(conn, course_code, section_label)
    if not section:
        raise ValueError("Section not found for the current trimester")

    if await _student_already_enrolled(conn, section["id"], student_user_id):
        raise ValueError("You are already enrolled in this section")

    pending = await fetch_one(
        conn,
        """
        SELECT id FROM section_enrollment_requests
        WHERE student_user_id = %s AND section_id = %s AND status = 'pending'
        """,
        (student_user_id, section["id"]),
    )
    if pending:
        raise ValueError("You already have a pending request for this section")

    return await execute_returning_id(
        conn,
        """
        INSERT INTO section_enrollment_requests (student_user_id, section_id, status, message)
        VALUES (%s, %s, 'pending', %s)
        """,
        (student_user_id, section["id"], message),
    )


async def list_requests_for_student(
    conn: pymysql.Connection, student_user_id: int
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        _REQUEST_LIST_SQL
        + """
        WHERE ser.student_user_id = %s
        ORDER BY ser.created_at DESC
        """,
        (student_user_id,),
    )


async def list_requests_admin(
    conn: pymysql.Connection, *, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        return await fetch_all(
            conn,
            _REQUEST_LIST_SQL + " WHERE ser.status = %s ORDER BY ser.created_at DESC",
            (status,),
        )
    return await fetch_all(
        conn,
        _REQUEST_LIST_SQL + " ORDER BY ser.created_at DESC",
    )


async def get_request(conn: pymysql.Connection, request_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        _REQUEST_LIST_SQL + " WHERE ser.id = %s",
        (request_id,),
    )


async def cancel_request(
    conn: pymysql.Connection, *, request_id: int, student_user_id: int
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE section_enrollment_requests
        SET status = 'cancelled', reviewed_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND student_user_id = %s AND status = 'pending'
        """,
        (request_id, student_user_id),
    )
    return count > 0


async def approve_request(
    conn: pymysql.Connection, *, request_id: int, reviewer_id: int
) -> dict[str, Any] | None:
    req = await fetch_one(
        conn,
        """
        SELECT id, student_user_id, section_id, status
        FROM section_enrollment_requests
        WHERE id = %s
        """,
        (request_id,),
    )
    if not req or req["status"] != "pending":
        return None

    section = await fetch_one(
        conn,
        """
        SELECT s.id, s.section_label, c.code AS course_code
        FROM sections s
        INNER JOIN courses c ON c.id = s.course_id
        WHERE s.id = %s AND s.is_active = 1
        """,
        (req["section_id"],),
    )
    if not section:
        return None

    await link_student_to_section(
        conn,
        section=section,
        student_user_id=req["student_user_id"],
        created_by_user_id=reviewer_id,
    )
    await execute(
        conn,
        """
        UPDATE section_enrollment_requests
        SET status = 'approved', reviewed_by_user_id = %s, reviewed_at = UTC_TIMESTAMP(3)
        WHERE id = %s
        """,
        (reviewer_id, request_id),
    )
    return await get_request(conn, request_id)


async def reject_request(
    conn: pymysql.Connection, *, request_id: int, reviewer_id: int
) -> dict[str, Any] | None:
    req = await fetch_one(
        conn,
        "SELECT id, status FROM section_enrollment_requests WHERE id = %s",
        (request_id,),
    )
    if not req or req["status"] != "pending":
        return None
    await execute(
        conn,
        """
        UPDATE section_enrollment_requests
        SET status = 'rejected', reviewed_by_user_id = %s, reviewed_at = UTC_TIMESTAMP(3)
        WHERE id = %s
        """,
        (reviewer_id, request_id),
    )
    return await get_request(conn, request_id)


async def delete_request(conn: pymysql.Connection, request_id: int) -> bool:
    count = await execute(
        conn,
        "DELETE FROM section_enrollment_requests WHERE id = %s AND status = 'pending'",
        (request_id,),
    )
    return count > 0


async def list_student_enrollments(
    conn: pymysql.Connection, student_user_id: int
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            se.id AS enrollment_id,
            s.id AS section_id,
            c.code AS course_code,
            c.title AS course_title,
            s.section_label,
            CONCAT(c.code, '::', s.section_label) AS section_key,
            se.enrolled_at
        FROM section_enrollments se
        INNER JOIN sections s ON s.id = se.section_id AND s.is_active = 1
        INNER JOIN courses c ON c.id = s.course_id
        WHERE se.student_user_id = %s AND se.dropped_at IS NULL
        ORDER BY c.code, s.section_label
        """,
        (student_user_id,),
    )


async def list_students_enrollment_summary(
    conn: pymysql.Connection, *, limit: int = 500
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            u.id,
            u.email,
            up.display_name AS name,
            d.code AS department_code,
            COUNT(DISTINCT se.id) AS enrollment_count
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id AND r.code = 'student'
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN departments d ON d.id = up.department_id
        LEFT JOIN section_enrollments se ON se.student_user_id = u.id AND se.dropped_at IS NULL
        LEFT JOIN sections s ON s.id = se.section_id AND s.is_active = 1
        GROUP BY u.id, u.email, up.display_name, d.code
        ORDER BY up.display_name, u.email
        LIMIT %s
        """,
        (limit,),
    )


async def admin_enroll_student(
    conn: pymysql.Connection,
    *,
    student_user_id: int,
    course_code: str,
    section_label: str,
    actor_user_id: int,
) -> dict[str, Any]:
    section = await academic_repo.find_section(conn, course_code, section_label)
    if not section:
        raise ValueError("Section not found for the current trimester")

    user = await fetch_one(
        conn,
        """
        SELECT u.id, r.code AS role_code
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (student_user_id,),
    )
    if not user or user.get("role_code") != "student":
        raise ValueError("User is not a student account")

    await link_student_to_section(
        conn,
        section=section,
        student_user_id=student_user_id,
        created_by_user_id=actor_user_id,
    )
    return section


async def admin_drop_student(
    conn: pymysql.Connection,
    *,
    student_user_id: int,
    course_code: str,
    section_label: str,
) -> bool:
    section = await academic_repo.find_section(conn, course_code, section_label)
    if not section:
        raise ValueError("Section not found for the current trimester")
    return await academic_repo.drop_student(conn, section["id"], student_user_id)


def _parse_csv_rows(content: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or missing a header row")
    normalized = {name.strip().lower(): name for name in reader.fieldnames}
    email_key = normalized.get("student_email") or normalized.get("email")
    course_key = normalized.get("course_code") or normalized.get("course")
    section_key = normalized.get("section_label") or normalized.get("section")
    if not email_key or not course_key or not section_key:
        raise ValueError(
            "CSV must include columns: student_email, course_code, section_label"
        )
    rows: list[dict[str, str]] = []
    for i, row in enumerate(reader, start=2):
        email = (row.get(email_key) or "").strip().lower()
        course_code = (row.get(course_key) or "").strip().upper()
        section_label = (row.get(section_key) or "").strip().upper()
        if not email and not course_code and not section_label:
            continue
        rows.append(
            {
                "row": str(i),
                "student_email": email,
                "course_code": course_code,
                "section_label": section_label,
            }
        )
    return rows


async def import_enrollments_from_csv(
    conn: pymysql.Connection,
    *,
    content: str,
    actor_user_id: int,
) -> dict[str, Any]:
    rows = _parse_csv_rows(content)
    enrolled = 0
    skipped = 0
    failed: list[dict[str, str]] = []

    for row in rows:
        line = row["row"]
        email = row["student_email"]
        course_code = row["course_code"]
        section_label = row["section_label"]

        if not email or not course_code or not section_label:
            failed.append(
                {
                    "row": line,
                    "student_email": email,
                    "course_code": course_code,
                    "section_label": section_label,
                    "reason": "Missing required fields",
                }
            )
            continue

        user = await fetch_one(
            conn,
            """
            SELECT u.id, u.email, r.code AS role_code
            FROM users u
            INNER JOIN roles r ON r.id = u.role_id
            WHERE u.email = %s
            """,
            (email.lower(),),
        )
        if not user:
            failed.append(
                {
                    "row": line,
                    "student_email": email,
                    "course_code": course_code,
                    "section_label": section_label,
                    "reason": "User not found",
                }
            )
            continue
        if user.get("role_code") != "student":
            failed.append(
                {
                    "row": line,
                    "student_email": email,
                    "course_code": course_code,
                    "section_label": section_label,
                    "reason": "Account is not a student",
                }
            )
            continue

        section = await academic_repo.find_section(conn, course_code, section_label)
        if not section:
            failed.append(
                {
                    "row": line,
                    "student_email": email,
                    "course_code": course_code,
                    "section_label": section_label,
                    "reason": "Section not found for current trimester",
                }
            )
            continue

        if await _student_already_enrolled(conn, section["id"], user["id"]):
            skipped += 1
            continue

        await link_student_to_section(
            conn,
            section=section,
            student_user_id=user["id"],
            created_by_user_id=actor_user_id,
        )
        enrolled += 1

    return {
        "total": len(rows),
        "enrolled": enrolled,
        "skipped_already_enrolled": skipped,
        "failed": len(failed),
        "errors": failed,
    }
