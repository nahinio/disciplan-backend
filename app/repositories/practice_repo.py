"""Raw SQL — practice problems, syllabus topics, past papers."""

from __future__ import annotations

import re
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


def _tag_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (slug or "tag")[:100]


async def _attach_tags_to_problems(
    conn: pymysql.Connection, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    problem_ids = [int(row["id"]) for row in rows]
    placeholders = ", ".join(["%s"] * len(problem_ids))
    tag_rows = await fetch_all(
        conn,
        f"""
        SELECT ppt.problem_id, pt.name
        FROM practice_problem_tags ppt
        INNER JOIN practice_tags pt ON pt.id = ppt.tag_id
        WHERE ppt.problem_id IN ({placeholders})
        ORDER BY pt.name
        """,
        tuple(problem_ids),
    )
    by_problem: dict[int, list[str]] = {}
    for row in tag_rows:
        by_problem.setdefault(int(row["problem_id"]), []).append(str(row["name"]))
    for row in rows:
        row["tags"] = by_problem.get(int(row["id"]), [])


async def set_problem_tags(
    conn: pymysql.Connection,
    *,
    problem_id: int,
    course_id: int,
    tag_names: list[str],
) -> None:
    await execute(conn, "DELETE FROM practice_problem_tags WHERE problem_id = %s", (problem_id,))
    if not tag_names:
        return

    tag_ids: list[int] = []
    for name in tag_names:
        slug = _tag_slug(name)
        existing = await fetch_one(
            conn,
            """
            SELECT id FROM practice_tags
            WHERE course_id = %s AND slug = %s
            LIMIT 1
            """,
            (course_id, slug),
        )
        if existing:
            tag_ids.append(int(existing["id"]))
            continue
        tag_id = await execute_returning_id(
            conn,
            """
            INSERT INTO practice_tags (course_id, name, slug)
            VALUES (%s, %s, %s)
            """,
            (course_id, name[:80], slug),
        )
        tag_ids.append(tag_id)

    for tag_id in tag_ids:
        await execute(
            conn,
            """
            INSERT IGNORE INTO practice_problem_tags (problem_id, tag_id)
            VALUES (%s, %s)
            """,
            (problem_id, tag_id),
        )


async def list_topics_with_counts(
    conn: pymysql.Connection, course_id: int
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            st.id, st.title AS topic, st.week_number, st.sort_order,
            COUNT(DISTINCT pp.id) AS problem_count,
            (
                SELECT COUNT(*)
                FROM blog_posts bp
                WHERE bp.topic_id = st.id AND bp.deleted_at IS NULL
            ) AS blog_count
        FROM syllabus_topics st
        LEFT JOIN practice_problems pp ON pp.topic_id = st.id
        WHERE st.course_id = %s
        GROUP BY st.id, st.title, st.week_number, st.sort_order
        ORDER BY st.sort_order, st.week_number
        """,
        (course_id,),
    )


async def list_problems(
    conn: pymysql.Connection,
    course_id: int,
    *,
    topic_id: int | None = None,
    assessment_type_code: str | None = None,
    section_id: int | None = None,
    central_only: bool = False,
) -> list[dict[str, Any]]:
    clauses = ["pp.course_id = %s"]
    params: list[Any] = [course_id]
    if central_only:
        clauses.append("pp.section_id IS NULL")
    elif section_id is not None:
        clauses.append("pp.section_id = %s")
        params.append(section_id)
    if topic_id is not None:
        clauses.append("pp.topic_id = %s")
        params.append(topic_id)
    if assessment_type_code:
        clauses.append("at.code = %s")
        params.append(assessment_type_code)

    where = " AND ".join(clauses)
    rows = await fetch_all(
        conn,
        f"""
        SELECT
            pp.id, pp.topic_id, pp.problem_number, pp.title,
            COALESCE(pp.question_text, pp.title) AS question,
            pp.answer_text AS answer,
            pp.difficulty_score, pp.section_id,
            qf.secure_url AS question_image_url,
            af.secure_url AS answer_image_url
        FROM practice_problems pp
        INNER JOIN assessment_types at ON at.id = pp.assessment_type_id
        LEFT JOIN files qf ON qf.id = pp.question_image_file_id AND qf.deleted_at IS NULL
        LEFT JOIN files af ON af.id = pp.answer_image_file_id AND af.deleted_at IS NULL
        WHERE {where}
        ORDER BY pp.problem_number ASC, pp.id ASC
        """,
        tuple(params),
    )
    await _attach_tags_to_problems(conn, rows)
    return rows


async def get_topic_for_course(
    conn: pymysql.Connection, topic_id: int, course_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, title, course_id
        FROM syllabus_topics
        WHERE id = %s AND course_id = %s
        LIMIT 1
        """,
        (topic_id, course_id),
    )


async def topic_delete_impact(
    conn: pymysql.Connection, *, topic_id: int, course_id: int
) -> dict[str, Any] | None:
    row = await fetch_one(
        conn,
        """
        SELECT
            st.id, st.title,
            (
                SELECT COUNT(*)
                FROM practice_problems pp
                WHERE pp.topic_id = st.id
            ) AS problem_count,
            (
                SELECT COUNT(*)
                FROM blog_posts bp
                WHERE bp.topic_id = st.id AND bp.deleted_at IS NULL
            ) AS blog_count
        FROM syllabus_topics st
        WHERE st.id = %s AND st.course_id = %s
        """,
        (topic_id, course_id),
    )
    return row


async def update_topic(
    conn: pymysql.Connection,
    *,
    topic_id: int,
    course_id: int,
    title: str,
) -> bool:
    clean = title.strip()
    if not clean:
        raise ValueError("Topic title is required")
    count = await execute(
        conn,
        """
        UPDATE syllabus_topics
        SET title = %s
        WHERE id = %s AND course_id = %s
        """,
        (clean, topic_id, course_id),
    )
    return count > 0


async def delete_topic_cascade(
    conn: pymysql.Connection, *, topic_id: int, course_id: int
) -> dict[str, int] | None:
    impact = await topic_delete_impact(conn, topic_id=topic_id, course_id=course_id)
    if not impact:
        return None

    await execute(
        conn,
        """
        UPDATE blog_posts
        SET deleted_at = UTC_TIMESTAMP(3)
        WHERE topic_id = %s AND deleted_at IS NULL
        """,
        (topic_id,),
    )
    await execute(conn, "DELETE FROM practice_problems WHERE topic_id = %s", (topic_id,))
    deleted = await execute(
        conn,
        "DELETE FROM syllabus_topics WHERE id = %s AND course_id = %s",
        (topic_id, course_id),
    )
    if not deleted:
        return None
    return {
        "blogs_deleted": int(impact["blog_count"] or 0),
        "problems_deleted": int(impact["problem_count"] or 0),
    }


async def create_topic(
    conn: pymysql.Connection,
    *,
    course_id: int,
    title: str,
    week_number: int | None,
    sort_order: int,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO syllabus_topics (course_id, title, week_number, sort_order)
        VALUES (%s, %s, %s, %s)
        """,
        (course_id, title, week_number, sort_order),
    )


async def next_problem_number(
    conn: pymysql.Connection, topic_id: int
) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COALESCE(MAX(problem_number), 0) AS max_num
        FROM practice_problems
        WHERE topic_id = %s
        """,
        (topic_id,),
    )
    return int((row or {}).get("max_num", 0)) + 1


async def create_problem(
    conn: pymysql.Connection,
    *,
    course_id: int,
    topic_id: int | None,
    creator_user_id: int,
    question: str,
    answer: str,
    assessment_type_code: str,
    difficulty_score: int,
    question_image_file_id: int | None = None,
    answer_image_file_id: int | None = None,
    section_id: int | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    atype = await fetch_one(
        conn, "SELECT id FROM assessment_types WHERE code = %s", (assessment_type_code,)
    )
    if not atype:
        raise ValueError(f"Unknown assessment type: {assessment_type_code}")

    problem_number = None
    if topic_id is not None:
        problem_number = await next_problem_number(conn, topic_id)

    plain_question = (
        question.replace("<", " ").replace(">", " ").replace("\n", " ").strip()
    )
    title = plain_question[:200] if plain_question else "Practice problem"
    if len(plain_question) > 200:
        title = plain_question[:197] + "..."

    problem_id = await execute_returning_id(
        conn,
        """
        INSERT INTO practice_problems (
            course_id, section_id, topic_id, problem_number, assessment_type_id, title,
            question_text, answer_text, question_image_file_id, answer_image_file_id,
            difficulty_score, created_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            course_id,
            section_id,
            topic_id,
            problem_number,
            atype["id"],
            title,
            question,
            answer,
            question_image_file_id,
            answer_image_file_id,
            difficulty_score,
            creator_user_id,
        ),
    )
    if tags:
        await set_problem_tags(
            conn, problem_id=problem_id, course_id=course_id, tag_names=tags
        )
    return {"id": problem_id, "problem_number": problem_number}


async def get_problem(conn: pymysql.Connection, problem_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, course_id, section_id, topic_id, title, question_text, answer_text
        FROM practice_problems
        WHERE id = %s
        """,
        (problem_id,),
    )


async def update_section_problem(
    conn: pymysql.Connection,
    problem_id: int,
    section_id: int,
    *,
    question: str | None = None,
    answer: str | None = None,
    topic_id: int | None = None,
    topic_id_set: bool = False,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if question is not None:
        plain = question.replace("<", " ").replace(">", " ").replace("\n", " ").strip()
        title = plain[:200] if len(plain) <= 200 else plain[:197] + "..."
        fields.extend(["question_text = %s", "title = %s"])
        params.extend([question, title])
    if answer is not None:
        fields.append("answer_text = %s")
        params.append(answer)
    if topic_id_set:
        fields.append("topic_id = %s")
        params.append(topic_id)
    if not fields:
        return False
    params.extend([problem_id, section_id])
    count = await execute(
        conn,
        f"""
        UPDATE practice_problems
        SET {", ".join(fields)}
        WHERE id = %s AND section_id = %s
        """,
        tuple(params),
    )
    return count > 0


async def delete_section_problem(
    conn: pymysql.Connection, problem_id: int, section_id: int
) -> bool:
    count = await execute(
        conn,
        "DELETE FROM practice_problems WHERE id = %s AND section_id = %s",
        (problem_id, section_id),
    )
    return count > 0


async def list_past_papers(conn: pymysql.Connection, course_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            pp.id, pp.title, pp.exam_year AS year, pp.created_at,
            f.original_filename, f.secure_url, f.size_bytes AS file_size
        FROM past_papers pp
        INNER JOIN files f ON f.id = pp.file_id AND f.deleted_at IS NULL
        WHERE pp.course_id = %s
        ORDER BY pp.exam_year DESC, pp.id DESC
        """,
        (course_id,),
    )


async def create_past_paper(
    conn: pymysql.Connection,
    *,
    course_id: int,
    title: str,
    exam_year: int,
    file_id: int,
    uploaded_by_user_id: int,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO past_papers (course_id, title, exam_year, file_id, uploaded_by_user_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (course_id, title, exam_year, file_id, uploaded_by_user_id),
    )
