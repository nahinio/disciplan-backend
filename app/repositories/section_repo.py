"""Raw SQL — section hub: announcements, doubts."""

from __future__ import annotations

import re
from typing import Any, Literal

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one
from app.repositories import notification_repo


async def _user_can_access_section(
    conn: pymysql.Connection, section_id: int, user_id: int, role_code: str
) -> bool:
    if role_code == "admin":
        return True
    if role_code == "faculty":
        row = await fetch_one(
            conn,
            "SELECT 1 FROM section_faculty WHERE section_id = %s AND faculty_user_id = %s",
            (section_id, user_id),
        )
        return row is not None
    row = await fetch_one(
        conn,
        """
        SELECT 1 FROM section_enrollments
        WHERE section_id = %s AND student_user_id = %s AND dropped_at IS NULL
        """,
        (section_id, user_id),
    )
    return row is not None


async def list_announcements(
    conn: pymysql.Connection, section_id: int, *, limit: int = 50
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            a.id, a.title, a.body, a.is_pinned, a.created_at, a.updated_at,
            up.display_name AS author_name,
            (SELECT COUNT(*) FROM section_announcement_comments c
             WHERE c.announcement_id = a.id AND c.deleted_at IS NULL) AS comment_count
        FROM section_announcements a
        INNER JOIN user_profiles up ON up.user_id = a.author_user_id
        WHERE a.section_id = %s AND a.deleted_at IS NULL
        ORDER BY a.is_pinned DESC, a.created_at DESC
        LIMIT %s
        """,
        (section_id, limit),
    )


async def create_announcement(
    conn: pymysql.Connection,
    *,
    section_id: int,
    author_user_id: int,
    title: str,
    body: str,
    is_pinned: bool = False,
) -> int:
    ann_id = await execute_returning_id(
        conn,
        """
        INSERT INTO section_announcements (section_id, author_user_id, title, body, is_pinned)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (section_id, author_user_id, title, body, int(is_pinned)),
    )

    # Notify enrolled students (complex INSERT SELECT)
    section = await fetch_one(
        conn,
        """
        SELECT c.code, s.section_label
        FROM sections s INNER JOIN courses c ON c.id = s.course_id
        WHERE s.id = %s
        """,
        (section_id,),
    )
    label = f"{section['code']} Sec {section['section_label']}" if section else "your section"
    await execute(
        conn,
        """
        INSERT INTO notifications (recipient_user_id, type_id, title, body_preview, reference_type_id, reference_id, action_path)
        SELECT
            se.student_user_id,
            (SELECT id FROM notification_types WHERE code = 'new_announcement' LIMIT 1),
            %s,
            LEFT(%s, 300),
            (SELECT id FROM reference_entity_types WHERE code = 'announcement' LIMIT 1),
            %s,
            CONCAT('/courses/', REPLACE(LOWER(%s), ' ', '-'), '/section?section=', %s, '&tab=announcements')
        FROM section_enrollments se
        WHERE se.section_id = %s AND se.dropped_at IS NULL AND se.student_user_id <> %s
        """,
        (
            f"New announcement in {label}",
            body,
            ann_id,
            section["code"] if section else "",
            section["section_label"] if section else "",
            section_id,
            author_user_id,
        ),
    )
    await execute(
        conn,
        """
        INSERT INTO notifications (recipient_user_id, type_id, title, body_preview, reference_type_id, reference_id, action_path)
        SELECT
            sf.faculty_user_id,
            (SELECT id FROM notification_types WHERE code = 'new_announcement' LIMIT 1),
            %s,
            LEFT(%s, 300),
            (SELECT id FROM reference_entity_types WHERE code = 'announcement' LIMIT 1),
            %s,
            CONCAT('/courses/', REPLACE(LOWER(%s), ' ', '-'), '/section?section=', %s, '&tab=announcements')
        FROM section_faculty sf
        WHERE sf.section_id = %s AND sf.faculty_user_id <> %s
        """,
        (
            f"New announcement in {label}",
            body,
            ann_id,
            section["code"] if section else "",
            section["section_label"] if section else "",
            section_id,
            author_user_id,
        ),
    )
    return ann_id


async def update_announcement(
    conn: pymysql.Connection,
    *,
    announcement_id: int,
    title: str | None = None,
    body: str | None = None,
    is_pinned: bool | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if body is not None:
        fields.append("body = %s")
        params.append(body)
    if is_pinned is not None:
        fields.append("is_pinned = %s")
        params.append(int(is_pinned))
    if not fields:
        return True
    fields.append("updated_at = UTC_TIMESTAMP(3)")
    params.append(announcement_id)
    count = await execute(
        conn,
        f"UPDATE section_announcements SET {', '.join(fields)} WHERE id = %s AND deleted_at IS NULL",
        tuple(params),
    )
    return count > 0


async def delete_announcement(conn: pymysql.Connection, announcement_id: int) -> bool:
    count = await execute(
        conn,
        "UPDATE section_announcements SET deleted_at = UTC_TIMESTAMP(3) WHERE id = %s AND deleted_at IS NULL",
        (announcement_id,),
    )
    return count > 0


def _fuzzy_tokens(q: str) -> list[str]:
    return [t for t in re.split(r"\W+", q.strip().lower()) if len(t) >= 2]


_FULLTEXT_SPECIAL = re.compile(r'[+\-><()~*"@]+')


def _sanitize_fulltext_term(term: str) -> str:
    return _FULLTEXT_SPECIAL.sub(" ", term.lower()).strip()


def _boolean_fulltext_query(tokens: list[str]) -> str:
    parts: list[str] = []
    for token in tokens:
        safe = _sanitize_fulltext_term(token)
        if len(safe) < 2:
            continue
        parts.append(f"{safe}*" if len(safe) >= 3 else safe)
    return " ".join(parts)


async def list_accessible_section_ids(
    conn: pymysql.Connection, user_id: int, role_code: str
) -> list[int]:
    """Sections the user may access in the current trimester."""
    if role_code == "admin":
        rows = await fetch_all(
            conn,
            """
            SELECT s.id
            FROM sections s
            INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
            """,
        )
    elif role_code == "faculty":
        rows = await fetch_all(
            conn,
            """
            SELECT s.id
            FROM sections s
            INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
            INNER JOIN section_faculty sf ON sf.section_id = s.id AND sf.faculty_user_id = %s
            """,
            (user_id,),
        )
    else:
        rows = await fetch_all(
            conn,
            """
            SELECT s.id
            FROM sections s
            INNER JOIN semesters sem ON sem.id = s.semester_id AND sem.is_current = 1
            INNER JOIN section_enrollments se ON se.section_id = s.id
              AND se.student_user_id = %s AND se.dropped_at IS NULL
            """,
            (user_id,),
        )
    return [int(r["id"]) for r in rows]


async def search_doubts(
    conn: pymysql.Connection,
    user_id: int,
    role_code: str,
    *,
    q: str = "",
    course_code: str | None = None,
    section_label: str | None = None,
    status: Literal["all", "resolved"] = "all",
    limit: int = 40,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Cross-section doubt search scoped to enrolled / assigned courses.
    Uses MySQL FULLTEXT + LIKE token matching for fuzzy recall.
    """
    section_ids = await list_accessible_section_ids(conn, user_id, role_code)
    if not section_ids:
        return [], 0

    placeholders = ",".join(["%s"] * len(section_ids))
    params: list[Any] = list(section_ids)

    filters = [f"d.section_id IN ({placeholders})", "d.deleted_at IS NULL"]

    if course_code:
        filters.append("c.code = %s")
        params.append(course_code.strip().upper())
    if section_label:
        filters.append("s.section_label = %s")
        params.append(section_label.strip().upper())

    if status == "resolved":
        filters.append(
            """
            (
              d.is_verified = 1
              OR EXISTS (
                SELECT 1 FROM section_doubt_answers fa
                WHERE fa.doubt_id = d.id AND fa.deleted_at IS NULL AND fa.is_faculty_answer = 1
              )
            )
            """
        )

    relevance_select = "0 AS relevance_score"
    relevance_params: list[Any] = []

    if q.strip():
        q_stripped = q.strip()
        tokens = _fuzzy_tokens(q_stripped)
        bool_q = _boolean_fulltext_query(tokens)
        like_whole = f"%{q_stripped}%"

        search_ors: list[str] = []
        search_params: list[Any] = []

        if bool_q:
            search_ors.append("MATCH(d.title, d.body) AGAINST (%s IN BOOLEAN MODE)")
            search_params.append(bool_q)

        search_ors.extend(
            [
                "LOWER(d.title) LIKE LOWER(%s)",
                "LOWER(d.body) LIKE LOWER(%s)",
                "UPPER(c.code) LIKE UPPER(%s)",
                "LOWER(COALESCE(up.display_name, '')) LIKE LOWER(%s)",
            ]
        )
        search_params.extend([like_whole, like_whole, like_whole, like_whole])

        answer_match_parts: list[str] = []
        if bool_q:
            answer_match_parts.append("MATCH(a.body) AGAINST (%s IN BOOLEAN MODE)")
        answer_match_parts.append("LOWER(a.body) LIKE LOWER(%s)")
        search_ors.append(
            f"""
            EXISTS (
              SELECT 1 FROM section_doubt_answers a
              WHERE a.doubt_id = d.id AND a.deleted_at IS NULL
                AND ({" OR ".join(answer_match_parts)})
            )
            """
        )
        if bool_q:
            search_params.append(bool_q)
        search_params.append(like_whole)

        token_ors: list[str] = []
        token_params: list[Any] = []
        for token in tokens:
            tok_like = f"%{token}%"
            token_ors.append(
                """
                (
                  LOWER(d.title) LIKE LOWER(%s) OR LOWER(d.body) LIKE LOWER(%s)
                  OR EXISTS (
                    SELECT 1 FROM section_doubt_answers a2
                    WHERE a2.doubt_id = d.id AND a2.deleted_at IS NULL
                      AND LOWER(a2.body) LIKE LOWER(%s)
                  )
                )
                """
            )
            token_params.extend([tok_like, tok_like, tok_like])

        if token_ors:
            search_ors.append(f"({' OR '.join(token_ors)})")
            search_params.extend(token_params)

        filters.append(f"({' OR '.join(search_ors)})")
        params.extend(search_params)

        nl_q = " ".join(tokens) if tokens else _sanitize_fulltext_term(q_stripped)
        relevance_select = """
            (
              IFNULL(MATCH(d.title, d.body) AGAINST (%s IN NATURAL LANGUAGE MODE), 0) * 4
              + IF(LOWER(d.title) LIKE LOWER(%s), 8, 0)
              + IF(LOWER(d.body) LIKE LOWER(%s), 4, 0)
              + IF(UPPER(c.code) LIKE UPPER(%s), 3, 0)
              + IF(LOWER(COALESCE(up.display_name, '')) LIKE LOWER(%s), 2, 0)
              + IF(EXISTS (
                  SELECT 1 FROM section_doubt_answers ar
                  WHERE ar.doubt_id = d.id AND ar.deleted_at IS NULL
                    AND LOWER(ar.body) LIKE LOWER(%s)
                ), 5, 0)
            ) AS relevance_score
        """
        relevance_params = [
            nl_q or q_stripped,
            like_whole,
            like_whole,
            like_whole,
            like_whole,
            like_whole,
        ]

    where_sql = " AND ".join(filters)

    count_row = await fetch_one(
        conn,
        f"""
        SELECT COUNT(*) AS n
        FROM section_doubts d
        INNER JOIN sections s ON s.id = d.section_id
        INNER JOIN courses c ON c.id = s.course_id
        LEFT JOIN user_profiles up ON up.user_id = d.author_user_id
        WHERE {where_sql}
        """,
        tuple(params),
    )
    total = int(count_row["n"]) if count_row else 0

    order_sql = (
        "relevance_score DESC, d.is_verified DESC, d.created_at DESC"
        if q.strip()
        else "d.is_verified DESC, d.created_at DESC"
    )

    # relevance_select placeholders appear before WHERE in the SELECT list
    select_params = (
        tuple(relevance_params + params + [limit, offset])
        if relevance_params
        else tuple(params + [limit, offset])
    )
    rows = await fetch_all(
        conn,
        f"""
        SELECT
            d.id, d.title, d.body, d.is_verified, d.accepted_answer_id, d.created_at,
            c.code AS course_code, s.section_label,
            COALESCE(up.display_name, 'Student') AS author_name,
            (SELECT COUNT(*) FROM section_doubt_answers a
             WHERE a.doubt_id = d.id AND a.deleted_at IS NULL) AS answer_count,
            (
              d.accepted_answer_id IS NOT NULL
              OR EXISTS (
                SELECT 1 FROM section_doubt_answers fa
                WHERE fa.doubt_id = d.id AND fa.deleted_at IS NULL AND fa.is_faculty_answer = 1
              )
            ) AS has_faculty_answer,
            {relevance_select}
        FROM section_doubts d
        INNER JOIN sections s ON s.id = d.section_id
        INNER JOIN courses c ON c.id = s.course_id
        LEFT JOIN user_profiles up ON up.user_id = d.author_user_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
        """,
        select_params,
    )
    return list(rows), total


async def list_doubts(
    conn: pymysql.Connection, section_id: int, *, limit: int = 50
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            d.id, d.title, d.body, d.is_verified, d.accepted_answer_id, d.created_at,
            up.display_name AS author_name,
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
            (SELECT COUNT(*) FROM section_doubt_answers a
             WHERE a.doubt_id = d.id AND a.deleted_at IS NULL) AS answer_count
        FROM section_doubts d
        INNER JOIN user_profiles up ON up.user_id = d.author_user_id
        LEFT JOIN section_doubt_votes dv ON dv.doubt_id = d.id
        LEFT JOIN vote_directions vd ON vd.id = dv.direction_id
        WHERE d.section_id = %s AND d.deleted_at IS NULL
        GROUP BY d.id, d.title, d.body, d.is_verified, d.created_at, up.display_name
        ORDER BY upvotes DESC, d.created_at DESC
        LIMIT %s
        """,
        (section_id, limit),
    )


async def create_doubt(
    conn: pymysql.Connection,
    *,
    section_id: int,
    author_user_id: int,
    title: str,
    body: str,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO section_doubts (section_id, author_user_id, title, body)
        VALUES (%s, %s, %s, %s)
        """,
        (section_id, author_user_id, title, body),
    )


async def get_doubt(conn: pymysql.Connection, doubt_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT
            d.id, d.section_id, d.title, d.body, d.is_verified, d.accepted_answer_id,
            d.created_at,
            up.display_name AS author_name,
            c.code AS course_code, s.section_label
        FROM section_doubts d
        INNER JOIN sections s ON s.id = d.section_id
        INNER JOIN courses c ON c.id = s.course_id
        INNER JOIN user_profiles up ON up.user_id = d.author_user_id
        WHERE d.id = %s AND d.deleted_at IS NULL
        """,
        (doubt_id,),
    )


async def list_answers(conn: pymysql.Connection, doubt_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            a.id, a.parent_answer_id, a.body, a.is_faculty_answer, a.is_faculty_endorsed,
            a.created_at,
            up.display_name AS author_name,
            r.code AS author_role_code
        FROM section_doubt_answers a
        INNER JOIN user_profiles up ON up.user_id = a.author_user_id
        INNER JOIN users u ON u.id = a.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        WHERE a.doubt_id = %s AND a.deleted_at IS NULL
        ORDER BY a.created_at ASC
        """,
        (doubt_id,),
    )


async def answer_doubt(
    conn: pymysql.Connection,
    *,
    doubt_id: int,
    author_user_id: int,
    body: str,
    is_faculty: bool,
    parent_answer_id: int | None = None,
) -> int:
    answer_id = await execute_returning_id(
        conn,
        """
        INSERT INTO section_doubt_answers (doubt_id, parent_answer_id, author_user_id, body, is_faculty_answer)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (doubt_id, parent_answer_id, author_user_id, body, int(is_faculty)),
    )

    doubt = await fetch_one(
        conn, "SELECT author_user_id, title FROM section_doubts WHERE id = %s", (doubt_id,)
    )
    if doubt and doubt["author_user_id"] != author_user_id:
        await notification_repo.create_notification(
            conn,
            recipient_user_id=doubt["author_user_id"],
            type_code="doubt_answered",
            title="Your doubt was answered",
            body_preview=body[:300],
            reference_type_code="doubt",
            reference_id=doubt_id,
        )
    return answer_id


async def verify_doubt(
    conn: pymysql.Connection,
    *,
    doubt_id: int,
    verifier_user_id: int,
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE section_doubts
        SET is_verified = 1,
            verified_by_user_id = %s,
            verified_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND deleted_at IS NULL
        """,
        (verifier_user_id, doubt_id),
    )
    return count > 0


class DoubtAcceptError(Exception):
    """Business rule violation when accepting a doubt answer."""


async def accept_doubt_answer(
    conn: pymysql.Connection,
    *,
    answer_id: int,
    verifier_user_id: int,
) -> dict[str, Any]:
    answer = await fetch_one(
        conn,
        """
        SELECT
            a.id, a.doubt_id, a.author_user_id, a.body,
            r.code AS author_role_code,
            d.section_id, d.accepted_answer_id, d.title AS doubt_title
        FROM section_doubt_answers a
        INNER JOIN users u ON u.id = a.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN section_doubts d ON d.id = a.doubt_id
        WHERE a.id = %s AND a.deleted_at IS NULL AND d.deleted_at IS NULL
        """,
        (answer_id,),
    )
    if not answer:
        raise DoubtAcceptError("not_found")
    if answer["author_role_code"] in ("faculty", "admin"):
        raise DoubtAcceptError("faculty_author")
    if answer["accepted_answer_id"]:
        raise DoubtAcceptError("already_accepted")

    await execute(
        conn,
        """
        UPDATE section_doubt_answers
        SET is_faculty_endorsed = 1
        WHERE id = %s
        """,
        (answer_id,),
    )
    await execute(
        conn,
        """
        UPDATE section_doubts
        SET is_verified = 1,
            accepted_answer_id = %s,
            verified_by_user_id = %s,
            verified_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND deleted_at IS NULL
        """,
        (answer_id, verifier_user_id, answer["doubt_id"]),
    )

    await notification_repo.create_notification(
        conn,
        recipient_user_id=answer["author_user_id"],
        type_code="doubt_solution_accepted",
        title="Faculty accepted your solution",
        body_preview=(answer["body"] or "")[:300],
        reference_type_code="doubt",
        reference_id=answer["doubt_id"],
    )

    return {
        "doubt_id": answer["doubt_id"],
        "author_user_id": answer["author_user_id"],
        "section_id": answer["section_id"],
    }


# ── Section resources ────────────────────────────────────────────────────────


async def list_resources(conn: pymysql.Connection, section_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            r.id, r.title, r.description, r.resource_kind, r.external_url,
            r.mime_category, r.sort_order, r.created_at,
            f.id AS file_id, f.original_filename, f.mime_type, f.secure_url AS file_url
        FROM section_resources r
        LEFT JOIN files f ON f.id = r.file_id
        WHERE r.section_id = %s AND r.deleted_at IS NULL
        ORDER BY r.sort_order ASC, r.created_at DESC
        """,
        (section_id,),
    )


async def create_resource(
    conn: pymysql.Connection,
    *,
    section_id: int,
    title: str,
    description: str | None,
    resource_kind: str,
    file_id: int | None,
    external_url: str | None,
    mime_category: str,
    created_by_user_id: int,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO section_resources (
            section_id, title, description, resource_kind, file_id,
            external_url, mime_category, created_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            section_id,
            title,
            description,
            resource_kind,
            file_id,
            external_url,
            mime_category,
            created_by_user_id,
        ),
    )


async def get_resource(
    conn: pymysql.Connection, resource_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, section_id, title, description, resource_kind, external_url, mime_category
        FROM section_resources
        WHERE id = %s AND deleted_at IS NULL
        """,
        (resource_id,),
    )


async def update_resource(
    conn: pymysql.Connection,
    resource_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    external_url: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
    if description is not None:
        fields.append("description = %s")
        params.append(description)
    if external_url is not None:
        fields.append("external_url = %s")
        params.append(external_url)
    if not fields:
        return False
    params.append(resource_id)
    count = await execute(
        conn,
        f"""
        UPDATE section_resources
        SET {", ".join(fields)}
        WHERE id = %s AND deleted_at IS NULL
        """,
        tuple(params),
    )
    return count > 0


async def delete_resource(conn: pymysql.Connection, resource_id: int) -> bool:
    count = await execute(
        conn,
        "UPDATE section_resources SET deleted_at = UTC_TIMESTAMP(3) WHERE id = %s AND deleted_at IS NULL",
        (resource_id,),
    )
    return count > 0


# ── Announcement comments ──────────────────────────────────────────────────────


async def list_announcement_comments(
    conn: pymysql.Connection, announcement_id: int
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            c.id, c.announcement_id, c.parent_comment_id, c.body,
            c.is_pinned, c.created_at,
            up.display_name AS author_name,
            r.code AS author_role_code,
            u.id AS author_user_id
        FROM section_announcement_comments c
        INNER JOIN users u ON u.id = c.author_user_id
        LEFT JOIN user_profiles up ON up.user_id = c.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        WHERE c.announcement_id = %s AND c.deleted_at IS NULL
        ORDER BY c.is_pinned DESC, c.created_at ASC
        """,
        (announcement_id,),
    )


async def create_announcement_comment(
    conn: pymysql.Connection,
    *,
    announcement_id: int,
    author_user_id: int,
    body: str,
    parent_comment_id: int | None = None,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO section_announcement_comments (
            announcement_id, parent_comment_id, author_user_id, body
        ) VALUES (%s, %s, %s, %s)
        """,
        (announcement_id, parent_comment_id, author_user_id, body),
    )


async def pin_announcement_comment(
    conn: pymysql.Connection,
    comment_id: int,
    *,
    pinned: bool,
    pinner_user_id: int,
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE section_announcement_comments
        SET is_pinned = %s,
            pinned_by_user_id = CASE WHEN %s = 1 THEN %s ELSE NULL END,
            pinned_at = CASE WHEN %s = 1 THEN UTC_TIMESTAMP(3) ELSE NULL END
        WHERE id = %s AND deleted_at IS NULL
        """,
        (int(pinned), int(pinned), pinner_user_id, int(pinned), comment_id),
    )
    return count > 0


async def delete_announcement_comment(
    conn: pymysql.Connection, comment_id: int, user_id: int, role_code: str
) -> bool:
    row = await fetch_one(
        conn,
        "SELECT author_user_id FROM section_announcement_comments WHERE id = %s AND deleted_at IS NULL",
        (comment_id,),
    )
    if not row:
        return False
    if role_code not in ("faculty", "admin") and row["author_user_id"] != user_id:
        return False
    count = await execute(
        conn,
        "UPDATE section_announcement_comments SET deleted_at = UTC_TIMESTAMP(3) WHERE id = %s",
        (comment_id,),
    )
    return count > 0


async def vote_doubt(
    conn: pymysql.Connection, doubt_id: int, voter_user_id: int, direction_code: str = "up"
) -> None:
    direction = await fetch_one(
        conn, "SELECT id FROM vote_directions WHERE code = %s", (direction_code,)
    )
    if not direction:
        return
    await execute(
        conn,
        """
        INSERT INTO section_doubt_votes (doubt_id, voter_user_id, direction_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE direction_id = VALUES(direction_id)
        """,
        (doubt_id, voter_user_id, direction["id"]),
    )
