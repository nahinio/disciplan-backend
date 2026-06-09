"""Raw SQL — course forum threads, replies, votes."""

from __future__ import annotations

from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


_THREAD_LIST_SELECT = """
        SELECT
            ft.id, ft.title, ft.body, ft.is_locked, ft.created_at,
            ft.author_user_id,
            c.code AS course_code,
            ftt.code AS thread_type_code,
            ftt.label AS thread_type_label,
            up.display_name AS author_name,
            r.code AS author_role_code,
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
            (SELECT COUNT(*) FROM forum_replies fr
             WHERE fr.thread_id = ft.id AND fr.deleted_at IS NULL) AS reply_count,
            GREATEST(
                ft.created_at,
                COALESCE(
                    (SELECT MAX(fr2.created_at) FROM forum_replies fr2
                     WHERE fr2.thread_id = ft.id AND fr2.deleted_at IS NULL),
                    ft.created_at
                )
            ) AS last_activity,
            COALESCE(
                (SELECT JSON_ARRAYAGG(f.secure_url)
                 FROM forum_thread_attachments fta
                 INNER JOIN files f ON f.id = fta.file_id AND f.deleted_at IS NULL
                 WHERE fta.thread_id = ft.id),
                JSON_ARRAY()
            ) AS image_urls
"""


async def list_threads(
    conn: pymysql.Connection,
    course_id: int,
    *,
    thread_type_code: str | None = None,
    author_user_id: int | None = None,
    limit: int = 50,
    viewer_user_id: int | None = None,
) -> list[dict[str, Any]]:
    type_clause = ""
    author_clause = ""
    params: list[Any] = []
    viewer_clause = ""
    if viewer_user_id is not None:
        viewer_clause = f""",
            EXISTS (
                SELECT 1 FROM forum_thread_votes ftv_viewer
                INNER JOIN vote_directions vd_viewer ON vd_viewer.id = ftv_viewer.direction_id
                WHERE ftv_viewer.thread_id = ft.id
                  AND ftv_viewer.voter_user_id = %s
                  AND vd_viewer.code = 'up'
            ) AS viewer_has_upvoted"""
        params.append(viewer_user_id)
    params.append(course_id)
    if thread_type_code:
        type_clause = " AND ftt.code = %s"
        params.append(thread_type_code)
    if author_user_id is not None:
        author_clause = " AND ft.author_user_id = %s"
        params.append(author_user_id)
    params.append(limit)
    return await fetch_all(
        conn,
        f"""
        {_THREAD_LIST_SELECT}{viewer_clause}
        FROM forum_threads ft
        INNER JOIN courses c ON c.id = ft.course_id
        INNER JOIN forum_thread_types ftt ON ftt.id = ft.thread_type_id
        INNER JOIN user_profiles up ON up.user_id = ft.author_user_id
        INNER JOIN users u ON u.id = ft.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        LEFT JOIN forum_thread_votes ftv ON ftv.thread_id = ft.id
        LEFT JOIN vote_directions vd ON vd.id = ftv.direction_id
        WHERE ft.course_id = %s AND ft.deleted_at IS NULL{type_clause}{author_clause}
        GROUP BY ft.id, ft.title, ft.body, ft.is_locked, ft.created_at,
                 ft.author_user_id, c.code, ftt.code, ftt.label, up.display_name, r.code
        ORDER BY last_activity DESC
        LIMIT %s
        """,
        tuple(params),
    )


async def list_feed(
    conn: pymysql.Connection,
    course_ids: list[int],
    *,
    thread_type_code: str | None = None,
    author_user_id: int | None = None,
    exclude_doubt: bool = True,
    sort: str = "recent",
    limit: int = 50,
    viewer_user_id: int | None = None,
) -> list[dict[str, Any]]:
    if not course_ids:
        return []

    placeholders = ", ".join(["%s"] * len(course_ids))
    type_clause = ""
    author_clause = ""
    params: list[Any] = []
    viewer_clause = ""
    if viewer_user_id is not None:
        viewer_clause = f""",
            EXISTS (
                SELECT 1 FROM forum_thread_votes ftv_viewer
                INNER JOIN vote_directions vd_viewer ON vd_viewer.id = ftv_viewer.direction_id
                WHERE ftv_viewer.thread_id = ft.id
                  AND ftv_viewer.voter_user_id = %s
                  AND vd_viewer.code = 'up'
            ) AS viewer_has_upvoted"""
        params.append(viewer_user_id)
    params.extend(course_ids)
    if thread_type_code:
        type_clause = " AND ftt.code = %s"
        params.append(thread_type_code)
    elif exclude_doubt:
        type_clause = " AND ftt.code != 'doubt'"
    if author_user_id is not None:
        author_clause = " AND ft.author_user_id = %s"
        params.append(author_user_id)

    order_clause = (
        "upvotes DESC, last_activity DESC"
        if sort == "top"
        else "last_activity DESC"
    )
    params.append(limit)

    return await fetch_all(
        conn,
        f"""
        SELECT * FROM (
            {_THREAD_LIST_SELECT}{viewer_clause}
            FROM forum_threads ft
            INNER JOIN courses c ON c.id = ft.course_id
            INNER JOIN forum_thread_types ftt ON ftt.id = ft.thread_type_id
            INNER JOIN user_profiles up ON up.user_id = ft.author_user_id
            INNER JOIN users u ON u.id = ft.author_user_id
            INNER JOIN roles r ON r.id = u.role_id
            LEFT JOIN forum_thread_votes ftv ON ftv.thread_id = ft.id
            LEFT JOIN vote_directions vd ON vd.id = ftv.direction_id
            WHERE ft.course_id IN ({placeholders})
              AND ft.deleted_at IS NULL{type_clause}{author_clause}
            GROUP BY ft.id, ft.title, ft.body, ft.is_locked, ft.created_at,
                     ft.author_user_id, c.code, ftt.code, ftt.label, up.display_name, r.code
        ) ranked
        ORDER BY {order_clause}
        LIMIT %s
        """,
        tuple(params),
    )


async def forum_stats(conn: pymysql.Connection, course_id: int) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN ftt.code = 'doubt' AND ft.is_locked = 0 THEN 1 ELSE 0 END) AS open_doubts
        FROM forum_threads ft
        INNER JOIN forum_thread_types ftt ON ftt.id = ft.thread_type_id
        WHERE ft.course_id = %s AND ft.deleted_at IS NULL
        """,
        (course_id,),
    )
    return {"total": int(row["total"] or 0), "open_doubts": int(row["open_doubts"] or 0)}


async def get_thread(
    conn: pymysql.Connection, thread_id: int, *, viewer_user_id: int | None = None
) -> dict[str, Any] | None:
    viewer_params: tuple[Any, ...] = (thread_id,)
    viewer_select = ""
    if viewer_user_id is not None:
        viewer_select = """,
            EXISTS (
                SELECT 1 FROM forum_thread_votes ftv_viewer
                INNER JOIN vote_directions vd_viewer ON vd_viewer.id = ftv_viewer.direction_id
                WHERE ftv_viewer.thread_id = ft.id
                  AND ftv_viewer.voter_user_id = %s
                  AND vd_viewer.code = 'up'
            ) AS viewer_has_upvoted"""
        viewer_params = (viewer_user_id, thread_id)

    row = await fetch_one(
        conn,
        f"""
        SELECT
            ft.id, ft.title, ft.body, ft.is_locked, ft.created_at,
            ft.course_id, c.code AS course_code,
            ftt.code AS thread_type_code,
            ftt.label AS thread_type_label,
            up.display_name AS author_name,
            u.id AS author_user_id,
            r.code AS author_role_code,
            COALESCE((
                SELECT SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END)
                FROM forum_thread_votes ftv
                INNER JOIN vote_directions vd ON vd.id = ftv.direction_id
                WHERE ftv.thread_id = ft.id
            ), 0) AS upvotes,
            (SELECT COUNT(*) FROM forum_replies fr
             WHERE fr.thread_id = ft.id AND fr.deleted_at IS NULL) AS reply_count,
            GREATEST(
                ft.created_at,
                COALESCE(
                    (SELECT MAX(fr2.created_at) FROM forum_replies fr2
                     WHERE fr2.thread_id = ft.id AND fr2.deleted_at IS NULL),
                    ft.created_at
                )
            ) AS last_activity,
            COALESCE(
                (SELECT JSON_ARRAYAGG(f.secure_url)
                 FROM forum_thread_attachments fta
                 INNER JOIN files f ON f.id = fta.file_id AND f.deleted_at IS NULL
                 WHERE fta.thread_id = ft.id),
                JSON_ARRAY()
            ) AS image_urls
            {viewer_select}
        FROM forum_threads ft
        INNER JOIN courses c ON c.id = ft.course_id
        INNER JOIN forum_thread_types ftt ON ftt.id = ft.thread_type_id
        INNER JOIN user_profiles up ON up.user_id = ft.author_user_id
        INNER JOIN users u ON u.id = ft.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        WHERE ft.id = %s AND ft.deleted_at IS NULL
        """,
        viewer_params,
    )
    return row


async def list_replies(conn: pymysql.Connection, thread_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            fr.id, fr.parent_reply_id, fr.body, fr.created_at,
            up.display_name AS author_name,
            u.id AS author_user_id,
            r.code AS author_role_code,
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes
        FROM forum_replies fr
        INNER JOIN user_profiles up ON up.user_id = fr.author_user_id
        INNER JOIN users u ON u.id = fr.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        LEFT JOIN forum_reply_votes frv ON frv.reply_id = fr.id
        LEFT JOIN vote_directions vd ON vd.id = frv.direction_id
        WHERE fr.thread_id = %s AND fr.deleted_at IS NULL
        GROUP BY fr.id, fr.parent_reply_id, fr.body, fr.created_at,
                 up.display_name, u.id, r.code
        ORDER BY fr.created_at ASC
        """,
        (thread_id,),
    )


async def _validate_image_files(
    conn: pymysql.Connection,
    *,
    file_ids: list[int],
    uploaded_by_user_id: int,
) -> None:
    if not file_ids:
        return
    if len(file_ids) > 6:
        raise ValueError("At most 6 images per post")
    placeholders = ", ".join(["%s"] * len(file_ids))
    rows = await fetch_all(
        conn,
        f"""
        SELECT id, uploaded_by_user_id, mime_type
        FROM files
        WHERE id IN ({placeholders}) AND deleted_at IS NULL
        """,
        tuple(file_ids),
    )
    if len(rows) != len(file_ids):
        raise ValueError("One or more image files were not found")
    for row in rows:
        if row["uploaded_by_user_id"] != uploaded_by_user_id:
            raise ValueError("You can only attach files you uploaded")
        mime = str(row["mime_type"] or "")
        if not mime.startswith("image/"):
            raise ValueError("Only image files can be attached to forum posts")


async def attach_thread_images(
    conn: pymysql.Connection, thread_id: int, file_ids: list[int]
) -> None:
    for file_id in file_ids:
        await execute(
            conn,
            """
            INSERT IGNORE INTO forum_thread_attachments (thread_id, file_id)
            VALUES (%s, %s)
            """,
            (thread_id, file_id),
        )


async def create_thread(
    conn: pymysql.Connection,
    *,
    course_id: int,
    author_user_id: int,
    thread_type_code: str,
    title: str,
    body: str,
    image_file_ids: list[int] | None = None,
) -> int:
    ttype = await fetch_one(
        conn, "SELECT id FROM forum_thread_types WHERE code = %s", (thread_type_code,)
    )
    if not ttype:
        raise ValueError(f"Unknown thread type: {thread_type_code}")
    file_ids = image_file_ids or []
    await _validate_image_files(
        conn, file_ids=file_ids, uploaded_by_user_id=author_user_id
    )
    thread_id = await execute_returning_id(
        conn,
        """
        INSERT INTO forum_threads (course_id, author_user_id, thread_type_id, title, body)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (course_id, author_user_id, ttype["id"], title, body),
    )
    if file_ids:
        await attach_thread_images(conn, thread_id, file_ids)
    return thread_id


async def add_reply(
    conn: pymysql.Connection,
    *,
    thread_id: int,
    author_user_id: int,
    body: str,
    parent_reply_id: int | None = None,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO forum_replies (thread_id, parent_reply_id, author_user_id, body)
        VALUES (%s, %s, %s, %s)
        """,
        (thread_id, parent_reply_id, author_user_id, body),
    )


async def vote_thread(
    conn: pymysql.Connection, thread_id: int, voter_user_id: int, direction_code: str
) -> int | None:
    direction = await fetch_one(
        conn, "SELECT id FROM vote_directions WHERE code = %s", (direction_code,)
    )
    if not direction:
        return None
    await execute(
        conn,
        """
        INSERT INTO forum_thread_votes (thread_id, voter_user_id, direction_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE direction_id = VALUES(direction_id)
        """,
        (thread_id, voter_user_id, direction["id"]),
    )
    thread = await fetch_one(
        conn, "SELECT author_user_id FROM forum_threads WHERE id = %s", (thread_id,)
    )
    return thread["author_user_id"] if thread else None


async def move_thread(
    conn: pymysql.Connection, thread_id: int, target_course_id: int
) -> bool:
    count = await execute(
        conn,
        "UPDATE forum_threads SET course_id = %s WHERE id = %s AND deleted_at IS NULL",
        (target_course_id, thread_id),
    )
    return count > 0


async def merge_threads(
    conn: pymysql.Connection, source_thread_id: int, target_thread_id: int
) -> bool:
    source = await fetch_one(
        conn,
        "SELECT id FROM forum_threads WHERE id = %s AND deleted_at IS NULL",
        (source_thread_id,),
    )
    target = await fetch_one(
        conn,
        "SELECT id FROM forum_threads WHERE id = %s AND deleted_at IS NULL",
        (target_thread_id,),
    )
    if not source or not target:
        return False
    await execute(
        conn,
        "UPDATE forum_replies SET thread_id = %s WHERE thread_id = %s",
        (target_thread_id, source_thread_id),
    )
    await execute(
        conn,
        "UPDATE forum_threads SET deleted_at = UTC_TIMESTAMP(3) WHERE id = %s",
        (source_thread_id,),
    )
    return True


async def delete_thread(conn: pymysql.Connection, thread_id: int) -> bool:
    count = await execute(
        conn,
        "UPDATE forum_threads SET deleted_at = UTC_TIMESTAMP(3) WHERE id = %s",
        (thread_id,),
    )
    return count > 0


async def update_thread_as_author(
    conn: pymysql.Connection,
    thread_id: int,
    author_user_id: int,
    *,
    title: str,
    body: str,
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE forum_threads
        SET title = %s, body = %s
        WHERE id = %s AND author_user_id = %s AND deleted_at IS NULL
        """,
        (title, body, thread_id, author_user_id),
    )
    return count > 0


async def update_reply_as_author(
    conn: pymysql.Connection,
    reply_id: int,
    author_user_id: int,
    *,
    body: str,
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE forum_replies
        SET body = %s
        WHERE id = %s AND author_user_id = %s AND deleted_at IS NULL
        """,
        (body, reply_id, author_user_id),
    )
    return count > 0


async def delete_thread_as_author(
    conn: pymysql.Connection, thread_id: int, author_user_id: int
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE forum_threads
        SET deleted_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND author_user_id = %s AND deleted_at IS NULL
        """,
        (thread_id, author_user_id),
    )
    return count > 0


async def delete_reply(conn: pymysql.Connection, reply_id: int) -> bool:
    count = await execute(
        conn,
        """
        UPDATE forum_replies
        SET deleted_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND deleted_at IS NULL
        """,
        (reply_id,),
    )
    return count > 0


async def delete_reply_as_author(
    conn: pymysql.Connection, reply_id: int, author_user_id: int
) -> bool:
    count = await execute(
        conn,
        """
        UPDATE forum_replies
        SET deleted_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND author_user_id = %s AND deleted_at IS NULL
        """,
        (reply_id, author_user_id),
    )
    return count > 0


async def vote_reply(
    conn: pymysql.Connection, reply_id: int, voter_user_id: int, direction_code: str
) -> int | None:
    direction = await fetch_one(
        conn, "SELECT id FROM vote_directions WHERE code = %s", (direction_code,)
    )
    if not direction:
        return None
    await execute(
        conn,
        """
        INSERT INTO forum_reply_votes (reply_id, voter_user_id, direction_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE direction_id = VALUES(direction_id)
        """,
        (reply_id, voter_user_id, direction["id"]),
    )
    reply = await fetch_one(
        conn, "SELECT author_user_id FROM forum_replies WHERE id = %s", (reply_id,)
    )
    return reply["author_user_id"] if reply else None
