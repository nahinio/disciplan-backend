"""Grade rubric, gradebook calculations, CGPA helpers."""

from __future__ import annotations

import re
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return (s[:30] if s else "component")


async def list_components(conn: pymysql.Connection, section_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT id, section_id, component_type, label, component_code, max_score,
               weight_percent, portal_id, team_id, sort_order, is_active, created_at
        FROM section_grade_components
        WHERE section_id = %s AND is_active = 1
        ORDER BY sort_order ASC, id ASC
        """,
        (section_id,),
    )


async def next_ct_code(conn: pymysql.Connection, section_id: int) -> str:
    rows = await fetch_all(
        conn,
        """
        SELECT component_code FROM section_grade_components
        WHERE section_id = %s AND component_type = 'ct'
        ORDER BY id ASC
        """,
        (section_id,),
    )
    n = len(rows) + 1
    return f"ct{n}"


async def get_ct_max(conn: pymysql.Connection, section_id: int) -> float | None:
    row = await fetch_one(
        conn,
        """
        SELECT max_score FROM section_grade_components
        WHERE section_id = %s AND component_type = 'ct' AND is_active = 1
        LIMIT 1
        """,
        (section_id,),
    )
    return float(row["max_score"]) if row else None


async def create_component(
    conn: pymysql.Connection,
    *,
    section_id: int,
    component_type: str,
    label: str,
    component_code: str,
    max_score: float,
    weight_percent: float,
    creator_user_id: int,
    portal_id: int | None = None,
    team_id: int | None = None,
    sort_order: int = 0,
) -> int:
    if component_type == "ct":
        existing_max = await get_ct_max(conn, section_id)
        if existing_max is not None and abs(existing_max - max_score) > 0.001:
            raise ValueError(
                f"All CT components must share the same max score ({existing_max})"
            )
    return await execute_returning_id(
        conn,
        """
        INSERT INTO section_grade_components (
            section_id, component_type, label, component_code, max_score,
            weight_percent, portal_id, team_id, sort_order, created_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            section_id,
            component_type,
            label,
            component_code,
            max_score,
            weight_percent,
            portal_id,
            team_id,
            sort_order,
            creator_user_id,
        ),
    )


async def update_component(
    conn: pymysql.Connection,
    component_id: int,
    *,
    label: str | None = None,
    max_score: float | None = None,
    weight_percent: float | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> bool:
    row = await fetch_one(
        conn,
        "SELECT section_id, component_type FROM section_grade_components WHERE id = %s",
        (component_id,),
    )
    if not row:
        return False
    if row["component_type"] == "ct" and max_score is not None:
        await execute(
            conn,
            """
            UPDATE section_grade_components SET max_score = %s
            WHERE section_id = %s AND component_type = 'ct' AND is_active = 1
            """,
            (max_score, row["section_id"]),
        )
    fields: list[str] = []
    params: list[Any] = []
    if label is not None:
        fields.append("label = %s")
        params.append(label)
    if max_score is not None and row["component_type"] != "ct":
        fields.append("max_score = %s")
        params.append(max_score)
    if weight_percent is not None:
        fields.append("weight_percent = %s")
        params.append(weight_percent)
    if sort_order is not None:
        fields.append("sort_order = %s")
        params.append(sort_order)
    if is_active is not None:
        fields.append("is_active = %s")
        params.append(1 if is_active else 0)
    if not fields:
        return True
    params.append(component_id)
    count = await execute(
        conn,
        f"UPDATE section_grade_components SET {', '.join(fields)} WHERE id = %s",
        tuple(params),
    )
    return count > 0


async def delete_component(conn: pymysql.Connection, component_id: int) -> bool:
    count = await execute(
        conn,
        "UPDATE section_grade_components SET is_active = 0 WHERE id = %s",
        (component_id,),
    )
    return count > 0


async def get_component_by_portal(
    conn: pymysql.Connection, portal_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, section_id, component_code, max_score, label
        FROM section_grade_components
        WHERE portal_id = %s AND is_active = 1
        LIMIT 1
        """,
        (portal_id,),
    )


async def get_component_by_team(
    conn: pymysql.Connection, team_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, section_id, component_code, max_score, label
        FROM section_grade_components
        WHERE team_id = %s AND is_active = 1
        LIMIT 1
        """,
        (team_id,),
    )


async def list_grade_scales(conn: pymysql.Connection) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT min_percent, max_percent, letter_grade, gpa_points
        FROM grade_scales ORDER BY sort_order ASC
        """,
    )


def letter_for_percent(scales: list[dict[str, Any]], percent: float) -> tuple[str, float]:
    for s in scales:
        if float(s["min_percent"]) <= percent <= float(s["max_percent"]):
            return str(s["letter_grade"]), float(s["gpa_points"])
    return "F", 0.0


def compute_student_summary(
    rubric: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    scales: list[dict[str, Any]],
) -> dict[str, Any]:
    grade_map = {g["component_code"]: g for g in grades}
    ct_rows = [c for c in rubric if c["component_type"] == "ct"]
    other_rows = [
        c
        for c in rubric
        if c["component_type"] in ("evaluation", "portal", "team", "attendance")
    ]

    ct_scores: list[dict[str, Any]] = []
    ct_max = float(ct_rows[0]["max_score"]) if ct_rows else None
    for ct in ct_rows:
        g = grade_map.get(ct["component_code"])
        ct_scores.append(
            {
                "code": ct["component_code"],
                "label": ct["label"],
                "score": float(g["score"]) if g else None,
                "max": float(ct["max_score"]),
            }
        )

    ct_values = [x["score"] for x in ct_scores if x["score"] is not None]
    ct_average = sum(ct_values) / len(ct_values) if ct_values else None

    evaluations: list[dict[str, Any]] = []
    weighted_sum = 0.0
    weight_total = 0.0

    if ct_rows and ct_average is not None and ct_max:
        ct_weight = sum(float(c["weight_percent"]) for c in ct_rows)
        if ct_weight > 0:
            pct = (ct_average / ct_max) * 100.0
            weighted_sum += pct * ct_weight
            weight_total += ct_weight

    for comp in other_rows:
        g = grade_map.get(comp["component_code"])
        score = float(g["score"]) if g else None
        max_s = float(comp["max_score"])
        w = float(comp["weight_percent"])
        evaluations.append(
            {
                "code": comp["component_code"],
                "label": comp["label"],
                "component_type": comp["component_type"],
                "score": score,
                "max": max_s,
                "weight_percent": w,
            }
        )
        if score is not None and w > 0 and max_s > 0:
            pct = (score / max_s) * 100.0
            weighted_sum += pct * w
            weight_total += w

    total_percent = (weighted_sum / weight_total) if weight_total > 0 else 0.0
    letter, gpa = letter_for_percent(scales, total_percent)

    return {
        "ct_scores": ct_scores,
        "ct_average": round(ct_average, 2) if ct_average is not None else None,
        "ct_max": ct_max,
        "evaluations": evaluations,
        "total_percent": round(total_percent, 2),
        "letter_grade": letter,
        "gpa_points": gpa,
    }


async def list_gradebook_enriched(
    conn: pymysql.Connection, section_id: int
) -> dict[str, Any]:
    rubric = await list_components(conn, section_id)
    scales = await list_grade_scales(conn)

    students = await fetch_all(
        conn,
        """
        SELECT u.id, up.display_name AS name, u.email
        FROM section_enrollments se
        INNER JOIN users u ON u.id = se.student_user_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE se.section_id = %s AND se.dropped_at IS NULL
        ORDER BY up.display_name, u.email
        """,
        (section_id,),
    )

    grades = await fetch_all(
        conn,
        """
        SELECT student_user_id, component_code, score, max_score, feedback
        FROM section_grades WHERE section_id = %s
        """,
        (section_id,),
    )
    grade_map: dict[int, list[dict[str, Any]]] = {}
    for g in grades:
        grade_map.setdefault(g["student_user_id"], []).append(g)

    items = []
    for s in students:
        student_grades = grade_map.get(s["id"], [])
        summary = compute_student_summary(rubric, student_grades, scales)
        items.append(
            {
                "id": s["id"],
                "name": s["name"],
                "email": s["email"],
                "components": student_grades,
                **summary,
            }
        )

    return {"rubric": rubric, "items": items, "scales": scales}


async def upsert_student_grade(
    conn: pymysql.Connection,
    *,
    section_id: int,
    student_user_id: int,
    recorder_user_id: int,
    component_code: str,
    score: float,
    max_score: float,
    feedback: str | None = None,
) -> None:
    await execute(
        conn,
        """
        INSERT INTO section_grades (
            section_id, student_user_id, component_code, score, max_score,
            feedback, recorded_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            score = VALUES(score),
            max_score = VALUES(max_score),
            feedback = VALUES(feedback),
            recorded_by_user_id = VALUES(recorded_by_user_id),
            recorded_at = UTC_TIMESTAMP(3)
        """,
        (
            section_id,
            student_user_id,
            component_code,
            score,
            max_score,
            feedback,
            recorder_user_id,
        ),
    )
    await recompute_student_semester_cgpa(conn, student_user_id, section_id)


async def recompute_student_semester_cgpa(
    conn: pymysql.Connection, student_user_id: int, section_id: int
) -> None:
    """Cache semester CGPA from weighted gradebook totals across enrolled sections."""
    row = await fetch_one(
        conn,
        """
        SELECT s.semester_id, c.credit_hours
        FROM sections s
        INNER JOIN courses c ON c.id = s.course_id
        WHERE s.id = %s
        """,
        (section_id,),
    )
    if not row:
        return

    semester_id = row["semester_id"]
    scales = await list_grade_scales(conn)
    enrollments = await fetch_all(
        conn,
        """
        SELECT se.section_id, c.credit_hours
        FROM section_enrollments se
        INNER JOIN sections s ON s.id = se.section_id AND s.semester_id = %s
        INNER JOIN courses c ON c.id = s.course_id
        WHERE se.student_user_id = %s AND se.dropped_at IS NULL
        """,
        (semester_id, student_user_id),
    )

    total_credits = 0.0
    quality_points = 0.0
    for enr in enrollments:
        rubric = await list_components(conn, enr["section_id"])
        grades = await fetch_all(
            conn,
            """
            SELECT component_code, score, max_score
            FROM section_grades
            WHERE section_id = %s AND student_user_id = %s
            """,
            (enr["section_id"], student_user_id),
        )
        summary = compute_student_summary(rubric, grades, scales)
        credits = float(enr["credit_hours"])
        total_credits += credits
        quality_points += summary["gpa_points"] * credits

    cgpa = round(quality_points / total_credits, 2) if total_credits > 0 else 0.0
    await execute(
        conn,
        """
        INSERT INTO student_semester_summaries (
            user_id, semester_id, total_credits, quality_points, cgpa
        ) VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            total_credits = VALUES(total_credits),
            quality_points = VALUES(quality_points),
            cgpa = VALUES(cgpa),
            updated_at = UTC_TIMESTAMP(3)
        """,
        (student_user_id, semester_id, total_credits, quality_points, cgpa),
    )
