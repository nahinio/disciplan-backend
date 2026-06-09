"""Content reports — submit, list moderation queue, resolve."""

from __future__ import annotations

from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one

ALLOWED_ENTITY_TYPES = frozenset(
    {"blog_post", "blog_comment", "forum_thread", "forum_reply"}
)

REASON_ALIASES: dict[str, str] = {
    "misinfo": "off_topic",
}


async def _lookup_id(
    conn: pymysql.Connection, table: str, code: str, *, code_col: str = "code"
) -> int | None:
    row = await fetch_one(
        conn, f"SELECT id FROM {table} WHERE {code_col} = %s", (code,)
    )
    return int(row["id"]) if row else None


async def create_report(
    conn: pymysql.Connection,
    *,
    reporter_user_id: int,
    entity_type_code: str,
    entity_id: int,
    reason_code: str,
    notes: str | None = None,
) -> int:
    if entity_type_code not in ALLOWED_ENTITY_TYPES:
        raise ValueError(f"Unsupported entity type: {entity_type_code}")

    normalized_reason = REASON_ALIASES.get(reason_code, reason_code)
    entity_type_id = await _lookup_id(conn, "reference_entity_types", entity_type_code)
    reason_id = await _lookup_id(conn, "report_reasons", normalized_reason)
    open_status_id = await _lookup_id(conn, "report_statuses", "open")
    if not entity_type_id or not reason_id or not open_status_id:
        raise ValueError("Invalid report configuration")

    existing = await fetch_one(
        conn,
        """
        SELECT cr.id
        FROM content_reports cr
        WHERE cr.reporter_user_id = %s
          AND cr.entity_type_id = %s
          AND cr.entity_id = %s
          AND cr.status_id = %s
        LIMIT 1
        """,
        (reporter_user_id, entity_type_id, entity_id, open_status_id),
    )
    if existing:
        raise ValueError("You have already reported this content")

    if not await _entity_exists(conn, entity_type_code, entity_id):
        raise ValueError("Reported content was not found")

    return await execute_returning_id(
        conn,
        """
        INSERT INTO content_reports (
            reporter_user_id, entity_type_id, entity_id, reason_id, status_id, notes
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (reporter_user_id, entity_type_id, entity_id, reason_id, open_status_id, notes),
    )


async def _entity_exists(
    conn: pymysql.Connection, entity_type_code: str, entity_id: int
) -> bool:
    queries = {
        "blog_post": "SELECT id FROM blog_posts WHERE id = %s AND deleted_at IS NULL",
        "blog_comment": "SELECT id FROM blog_comments WHERE id = %s AND deleted_at IS NULL",
        "forum_thread": "SELECT id FROM forum_threads WHERE id = %s AND deleted_at IS NULL",
        "forum_reply": "SELECT id FROM forum_replies WHERE id = %s AND deleted_at IS NULL",
    }
    sql = queries.get(entity_type_code)
    if not sql:
        return False
    row = await fetch_one(conn, sql, (entity_id,))
    return row is not None


async def list_reports_admin(
    conn: pymysql.Connection,
    *,
    status_code: str = "open",
    entity_type_code: str | None = None,
    entity_type_codes: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    status_id = await _lookup_id(conn, "report_statuses", status_code)
    if not status_id:
        return []

    clauses = ["cr.status_id = %s"]
    params: list[Any] = [status_id]

    codes: list[str] = []
    if entity_type_codes:
        codes = list(entity_type_codes)
    elif entity_type_code:
        codes = [entity_type_code]

    if codes:
        type_ids: list[int] = []
        for code in codes:
            entity_type_id = await _lookup_id(conn, "reference_entity_types", code)
            if entity_type_id:
                type_ids.append(entity_type_id)
        if not type_ids:
            return []
        placeholders = ", ".join(["%s"] * len(type_ids))
        clauses.append(f"cr.entity_type_id IN ({placeholders})")
        params.extend(type_ids)

    params.extend([limit, offset])
    where = " AND ".join(clauses)

    rows = await fetch_all(
        conn,
        f"""
        SELECT
            cr.id, cr.entity_id, cr.notes, cr.created_at,
            ret.code AS entity_type_code,
            ret.label AS entity_type_label,
            rr.code AS reason_code,
            rr.label AS reason_label,
            rs.code AS status_code,
            up.display_name AS reporter_name,
            ru.email AS reporter_email
        FROM content_reports cr
        INNER JOIN reference_entity_types ret ON ret.id = cr.entity_type_id
        INNER JOIN report_reasons rr ON rr.id = cr.reason_id
        INNER JOIN report_statuses rs ON rs.id = cr.status_id
        INNER JOIN users ru ON ru.id = cr.reporter_user_id
        LEFT JOIN user_profiles up ON up.user_id = cr.reporter_user_id
        WHERE {where}
        ORDER BY cr.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    return await _attach_previews(conn, rows)


async def _attach_previews(
    conn: pymysql.Connection, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not rows:
        return rows

    by_type: dict[str, list[int]] = {}
    for row in rows:
        code = str(row["entity_type_code"])
        by_type.setdefault(code, []).append(int(row["entity_id"]))

    previews: dict[str, dict[int, dict[str, Any]]] = {
        t: await _fetch_previews(conn, t, ids) for t, ids in by_type.items()
    }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        entity_type = str(row["entity_type_code"])
        entity_id = int(row["entity_id"])
        preview = previews.get(entity_type, {}).get(entity_id, {})
        enriched.append({**row, **preview})
    return enriched


async def _fetch_previews(
    conn: pymysql.Connection, entity_type_code: str, entity_ids: list[int]
) -> dict[int, dict[str, Any]]:
    if not entity_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(entity_ids))
    params = tuple(entity_ids)

    if entity_type_code == "blog_post":
        sql = f"""
            SELECT bp.id AS entity_id, bp.title AS preview_title, bp.excerpt AS preview_body,
                   c.code AS course_code, up.display_name AS content_author
            FROM blog_posts bp
            INNER JOIN courses c ON c.id = bp.course_id
            INNER JOIN user_profiles up ON up.user_id = bp.author_user_id
            WHERE bp.id IN ({placeholders}) AND bp.deleted_at IS NULL
        """
    elif entity_type_code == "blog_comment":
        sql = f"""
            SELECT bc.id AS entity_id,
                   CONCAT('Comment on: ', bp.title) AS preview_title,
                   bc.body AS preview_body,
                   c.code AS course_code,
                   up.display_name AS content_author
            FROM blog_comments bc
            INNER JOIN blog_posts bp ON bp.id = bc.post_id
            INNER JOIN courses c ON c.id = bp.course_id
            INNER JOIN user_profiles up ON up.user_id = bc.author_user_id
            WHERE bc.id IN ({placeholders}) AND bc.deleted_at IS NULL
        """
    elif entity_type_code == "forum_thread":
        sql = f"""
            SELECT ft.id AS entity_id, ft.title AS preview_title, ft.body AS preview_body,
                   c.code AS course_code, up.display_name AS content_author
            FROM forum_threads ft
            INNER JOIN courses c ON c.id = ft.course_id
            INNER JOIN user_profiles up ON up.user_id = ft.author_user_id
            WHERE ft.id IN ({placeholders}) AND ft.deleted_at IS NULL
        """
    elif entity_type_code == "forum_reply":
        sql = f"""
            SELECT fr.id AS entity_id,
                   CONCAT('Reply on: ', ft.title) AS preview_title,
                   fr.body AS preview_body,
                   c.code AS course_code,
                   up.display_name AS content_author
            FROM forum_replies fr
            INNER JOIN forum_threads ft ON ft.id = fr.thread_id
            INNER JOIN courses c ON c.id = ft.course_id
            INNER JOIN user_profiles up ON up.user_id = fr.author_user_id
            WHERE fr.id IN ({placeholders}) AND fr.deleted_at IS NULL
        """
    else:
        return {}

    rows = await fetch_all(conn, sql, params)
    return {
        int(r["entity_id"]): {
            "preview_title": r.get("preview_title"),
            "preview_body": r.get("preview_body"),
            "course_code": r.get("course_code"),
            "content_author": r.get("content_author"),
        }
        for r in rows
    }


async def resolve_report(
    conn: pymysql.Connection,
    report_id: int,
    *,
    resolver_user_id: int,
    status_code: str,
) -> bool:
    status_id = await _lookup_id(conn, "report_statuses", status_code)
    if not status_id:
        return False
    count = await execute(
        conn,
        """
        UPDATE content_reports
        SET status_id = %s,
            resolved_at = UTC_TIMESTAMP(3),
            resolved_by_user_id = %s
        WHERE id = %s
        """,
        (status_id, resolver_user_id, report_id),
    )
    return count > 0


async def get_report(conn: pymysql.Connection, report_id: int) -> dict[str, Any] | None:
    row = await fetch_one(
        conn,
        """
        SELECT cr.id, cr.entity_id, cr.notes, cr.reporter_user_id,
               ret.code AS entity_type_code
        FROM content_reports cr
        INNER JOIN reference_entity_types ret ON ret.id = cr.entity_type_id
        WHERE cr.id = %s
        """,
        (report_id,),
    )
    if not row:
        return None
    enriched = await _attach_previews(conn, [row])
    return enriched[0] if enriched else None
