"""Portal/team grading sync with gradebook and faculty planner tasks."""

from __future__ import annotations

from datetime import datetime

import pymysql

from app.db.session import execute, fetch_all, fetch_one
from app.repositories import grade_repo, task_planner_repo


async def _faculty_for_section(conn: pymysql.Connection, section_id: int) -> list[int]:
    rows = await fetch_all(
        conn,
        "SELECT faculty_user_id AS id FROM section_faculty WHERE section_id = %s",
        (section_id,),
    )
    return [r["id"] for r in rows]


async def _enrolled_count(conn: pymysql.Connection, section_id: int) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COUNT(*) AS n FROM section_enrollments
        WHERE section_id = %s AND dropped_at IS NULL
        """,
        (section_id,),
    )
    return int(row["n"]) if row else 0


async def _graded_count(conn: pymysql.Connection, portal_id: int) -> int:
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


async def on_portal_created(
    conn: pymysql.Connection,
    *,
    portal_id: int,
    section_id: int,
    course_id: int,
    creator_user_id: int,
    title: str,
    closes_at: datetime,
    max_score: float,
) -> None:
    code = f"portal_{portal_id}"
    try:
        await grade_repo.create_component(
            conn,
            section_id=section_id,
            component_type="portal",
            label=title,
            component_code=code,
            max_score=max_score,
            weight_percent=0,
            creator_user_id=creator_user_id,
            portal_id=portal_id,
        )
    except Exception:
        pass

    grading_type = await task_planner_repo.get_planner_type_id(conn, "grading")
    priority = await fetch_one(
        conn, "SELECT id FROM task_priorities WHERE code = 'high' LIMIT 1"
    )
    if not grading_type or not priority:
        return

    faculty_ids = await _faculty_for_section(conn, section_id)
    for fid in faculty_ids:
        await task_planner_repo.create_planner_task(
            conn,
            user_id=fid,
            title=f"Grade: {title}",
            priority_id=priority["id"],
            course_id=course_id,
            section_id=section_id,
            planner_task_type_id=grading_type,
            due_at=closes_at,
            source="manual",
        )


async def _update_grading_tasks(
    conn: pymysql.Connection,
    *,
    portal_id: int,
    section_id: int,
) -> None:
    enrolled = await _enrolled_count(conn, section_id)
    graded = await _graded_count(conn, portal_id)
    pct = round((graded / enrolled) * 100) if enrolled else 0
    portal = await fetch_one(
        conn, "SELECT title FROM assessment_portals WHERE id = %s", (portal_id,)
    )
    if not portal:
        return
    title_pattern = f"Grade: {portal['title']}"
    faculty_ids = await _faculty_for_section(conn, section_id)
    for fid in faculty_ids:
        task = await fetch_one(
            conn,
            """
            SELECT id FROM user_tasks
            WHERE user_id = %s AND section_id = %s AND title = %s
              AND is_skipped = 0
            ORDER BY id DESC LIMIT 1
            """,
            (fid, section_id, title_pattern),
        )
        if task:
            await task_planner_repo.update_planner_task(
                conn,
                fid,
                task["id"],
                completion_percent=min(100, pct),
                is_completed=1 if pct >= 100 and enrolled > 0 else 0,
            )
            await task_planner_repo.recompute_weights(conn, fid)


async def on_submission_graded(
    conn: pymysql.Connection,
    *,
    submission_id: int,
    grader_user_id: int,
    score: float,
    feedback: str | None,
) -> None:
    sub = await fetch_one(
        conn,
        """
        SELECT sub.student_user_id, sub.portal_id, sub.score,
               ap.section_id, ap.max_score, ap.title
        FROM submissions sub
        INNER JOIN assessment_portals ap ON ap.id = sub.portal_id
        WHERE sub.id = %s
        """,
        (submission_id,),
    )
    if not sub:
        return

    comp = await grade_repo.get_component_by_portal(conn, sub["portal_id"])
    if comp:
        await grade_repo.upsert_student_grade(
            conn,
            section_id=sub["section_id"],
            student_user_id=sub["student_user_id"],
            recorder_user_id=grader_user_id,
            component_code=comp["component_code"],
            score=score,
            max_score=float(comp["max_score"]),
            feedback=feedback,
        )

    await _update_grading_tasks(conn, portal_id=sub["portal_id"], section_id=sub["section_id"])


async def on_team_graded(
    conn: pymysql.Connection,
    *,
    team_id: int,
    section_id: int,
    grader_user_id: int,
    score: float,
    max_score: float,
    label: str,
    member_user_ids: list[int],
    feedback: str | None = None,
) -> None:
    comp = await grade_repo.get_component_by_team(conn, team_id)
    if not comp:
        code = f"team_{team_id}"
        await grade_repo.create_component(
            conn,
            section_id=section_id,
            component_type="team",
            label=label,
            component_code=code,
            max_score=max_score,
            weight_percent=0,
            creator_user_id=grader_user_id,
            team_id=team_id,
        )
        comp = await grade_repo.get_component_by_team(conn, team_id)
    if not comp:
        return

    for uid in member_user_ids:
        await grade_repo.upsert_student_grade(
            conn,
            section_id=section_id,
            student_user_id=uid,
            recorder_user_id=grader_user_id,
            component_code=comp["component_code"],
            score=score,
            max_score=max_score,
            feedback=feedback,
        )
