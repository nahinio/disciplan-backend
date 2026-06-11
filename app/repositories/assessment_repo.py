"""Raw SQL — assessment portals, submissions, section grades."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one
from app.repositories import notification_repo
from app.repositories.section_repo import _user_can_access_section


async def list_portals(conn: pymysql.Connection, section_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            ap.id, ap.title, ap.description, ap.opens_at, ap.closes_at, ap.max_score,
            ap.created_at,
            at.code AS assessment_type_code,
            at.label AS assessment_type_label,
            (SELECT COUNT(*) FROM submissions sub WHERE sub.portal_id = ap.id) AS submission_count
        FROM assessment_portals ap
        INNER JOIN assessment_types at ON at.id = ap.assessment_type_id
        WHERE ap.section_id = %s
        ORDER BY ap.closes_at DESC
        """,
        (section_id,),
    )


async def create_portal(
    conn: pymysql.Connection,
    *,
    section_id: int,
    creator_user_id: int,
    title: str,
    description: str | None,
    assessment_type_code: str,
    opens_at: datetime,
    closes_at: datetime,
    max_score: float,
) -> int:
    atype = await fetch_one(
        conn, "SELECT id FROM assessment_types WHERE code = %s", (assessment_type_code,)
    )
    if not atype:
        raise ValueError(f"Unknown assessment type: {assessment_type_code}")
    return await execute_returning_id(
        conn,
        """
        INSERT INTO assessment_portals (
            section_id, assessment_type_id, title, description,
            opens_at, closes_at, max_score, created_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (section_id, atype["id"], title, description, opens_at, closes_at, max_score, creator_user_id),
    )


async def update_portal(
    conn: pymysql.Connection,
    portal_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    opens_at: datetime | None = None,
    closes_at: datetime | None = None,
    max_score: float | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if opens_at is not None:
        fields.append("opens_at = %s")
        params.append(opens_at)
    if closes_at is not None:
        fields.append("closes_at = %s")
        params.append(closes_at)
    if max_score is not None:
        fields.append("max_score = %s")
        params.append(max_score)
    if not fields:
        return True
    params.append(portal_id)
    count = await execute(
        conn,
        f"UPDATE assessment_portals SET {', '.join(fields)} WHERE id = %s",
        tuple(params),
    )
    return count > 0


async def delete_portal(conn: pymysql.Connection, portal_id: int) -> bool:
    await execute(conn, "DELETE FROM submission_files WHERE submission_id IN (SELECT id FROM submissions WHERE portal_id = %s)", (portal_id,))
    await execute(conn, "DELETE FROM submissions WHERE portal_id = %s", (portal_id,))
    count = await execute(conn, "DELETE FROM assessment_portals WHERE id = %s", (portal_id,))
    return count > 0


async def get_portal(conn: pymysql.Connection, portal_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT
            ap.id, ap.section_id, ap.title, ap.description,
            ap.opens_at, ap.closes_at, ap.max_score, ap.created_at,
            at.code AS assessment_type_code,
            c.code AS course_code, s.section_label
        FROM assessment_portals ap
        INNER JOIN assessment_types at ON at.id = ap.assessment_type_id
        INNER JOIN sections s ON s.id = ap.section_id
        INNER JOIN courses c ON c.id = s.course_id
        WHERE ap.id = %s
        """,
        (portal_id,),
    )


async def get_student_submission(
    conn: pymysql.Connection, portal_id: int, student_user_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT
            sub.id, sub.submitted_at, sub.score, sub.feedback, sub.graded_at,
            ss.code AS status_code,
            f.original_filename AS submitted_file,
            f.secure_url AS file_url
        FROM submissions sub
        INNER JOIN submission_statuses ss ON ss.id = sub.status_id
        LEFT JOIN submission_files sf ON sf.submission_id = sub.id
        LEFT JOIN files f ON f.id = sf.file_id AND f.deleted_at IS NULL
        WHERE sub.portal_id = %s AND sub.student_user_id = %s
        """,
        (portal_id, student_user_id),
    )


async def list_submissions(conn: pymysql.Connection, portal_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            sub.id, sub.student_user_id AS student_id,
            up.display_name AS student_name, u.email AS student_email,
            sub.submitted_at, sub.score AS marks_obtained,
            ap.max_score AS max_marks, sub.feedback, sub.graded_at,
            ss.code AS status_code,
            f.original_filename AS submitted_file,
            f.secure_url AS file_url
        FROM submissions sub
        INNER JOIN assessment_portals ap ON ap.id = sub.portal_id
        INNER JOIN users u ON u.id = sub.student_user_id
        LEFT JOIN user_profiles up ON up.user_id = sub.student_user_id
        INNER JOIN submission_statuses ss ON ss.id = sub.status_id
        LEFT JOIN submission_files sf ON sf.submission_id = sub.id
        LEFT JOIN files f ON f.id = sf.file_id AND f.deleted_at IS NULL
        WHERE sub.portal_id = %s
        ORDER BY sub.submitted_at DESC
        """,
        (portal_id,),
    )


async def submit(
    conn: pymysql.Connection,
    *,
    portal_id: int,
    student_user_id: int,
    file_id: int,
) -> int:
    status = await fetch_one(
        conn, "SELECT id FROM submission_statuses WHERE code = 'submitted' LIMIT 1"
    )
    if not status:
        raise ValueError("Missing submission status lookup")

    existing = await fetch_one(
        conn,
        "SELECT id FROM submissions WHERE portal_id = %s AND student_user_id = %s",
        (portal_id, student_user_id),
    )
    if existing:
        await execute(
            conn,
            """
            UPDATE submissions
            SET status_id = %s, submitted_at = UTC_TIMESTAMP(3)
            WHERE id = %s
            """,
            (status["id"], existing["id"]),
        )
        sub_id = existing["id"]
        await execute(conn, "DELETE FROM submission_files WHERE submission_id = %s", (sub_id,))
    else:
        sub_id = await execute_returning_id(
            conn,
            """
            INSERT INTO submissions (portal_id, student_user_id, status_id)
            VALUES (%s, %s, %s)
            """,
            (portal_id, student_user_id, status["id"]),
        )

    await execute(
        conn,
        "INSERT INTO submission_files (submission_id, file_id) VALUES (%s, %s)",
        (sub_id, file_id),
    )
    return sub_id


async def grade_submission(
    conn: pymysql.Connection,
    *,
    submission_id: int,
    grader_user_id: int,
    score: float,
    feedback: str | None,
) -> bool:
    status = await fetch_one(
        conn, "SELECT id FROM submission_statuses WHERE code = 'graded' LIMIT 1"
    )
    if not status:
        return False

    count = await execute(
        conn,
        """
        UPDATE submissions
        SET status_id = %s, score = %s, feedback = %s,
            graded_by_user_id = %s, graded_at = UTC_TIMESTAMP(3)
        WHERE id = %s
        """,
        (status["id"], score, feedback, grader_user_id, submission_id),
    )
    if count > 0:
        sub = await fetch_one(
            conn, "SELECT student_user_id, portal_id FROM submissions WHERE id = %s", (submission_id,)
        )
        if sub:
            portal = await get_portal(conn, sub["portal_id"])
            if portal:
                slug = portal["course_code"].lower().replace(" ", "-")
                action_path = (
                    f"/courses/{slug}/submissions?section={portal['section_label']}"
                )
            else:
                action_path = "/dashboard"
            await notification_repo.create_notification(
                conn,
                recipient_user_id=sub["student_user_id"],
                type_code="submission_graded",
                title="Submission graded",
                body_preview=feedback[:300] if feedback else "Your submission has been graded",
                reference_type_code="submission",
                reference_id=submission_id,
                action_path=action_path,
            )
    return count > 0


async def upsert_grade(
    conn: pymysql.Connection,
    *,
    section_id: int,
    student_user_id: int,
    recorder_user_id: int,
    component_code: str,
    score: float,
    max_score: float,
) -> None:
    await execute(
        conn,
        """
        INSERT INTO section_grades (
            section_id, student_user_id, component_code, score, max_score, recorded_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            score = VALUES(score),
            max_score = VALUES(max_score),
            recorded_by_user_id = VALUES(recorded_by_user_id),
            recorded_at = UTC_TIMESTAMP(3)
        """,
        (section_id, student_user_id, component_code, score, max_score, recorder_user_id),
    )


async def ensure_section_access(
    conn: pymysql.Connection, section_id: int, user_id: int, role_code: str
) -> bool:
    return await _user_can_access_section(conn, section_id, user_id, role_code)
