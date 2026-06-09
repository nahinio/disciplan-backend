"""Raw SQL — blog posts, comments, votes."""

from __future__ import annotations

import re
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


def _slugify(title: str, topic_id: int | None = None) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = slug[:200] or "post"
    if topic_id is not None:
        suffix = f"-t{topic_id}"
        slug = f"{slug}{suffix}"[:280]
    return slug


async def _unique_slug(
    conn: pymysql.Connection, course_id: int, title: str, topic_id: int | None = None
) -> str:
    base = _slugify(title, topic_id)
    slug = base
    suffix = 2
    while True:
        existing = await fetch_one(
            conn,
            """
            SELECT id FROM blog_posts
            WHERE course_id = %s AND slug = %s AND deleted_at IS NULL
            LIMIT 1
            """,
            (course_id, slug),
        )
        if not existing:
            return slug
        extra = f"-{suffix}"
        slug = f"{base[: 280 - len(extra)]}{extra}"
        suffix += 1


def _tag_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (slug or "tag")[:100]


async def _attach_tags_to_posts(
    conn: pymysql.Connection, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    post_ids = [int(row["id"]) for row in rows]
    placeholders = ", ".join(["%s"] * len(post_ids))
    tag_rows = await fetch_all(
        conn,
        f"""
        SELECT bpt.post_id, bt.name
        FROM blog_post_tags bpt
        INNER JOIN blog_tags bt ON bt.id = bpt.tag_id
        WHERE bpt.post_id IN ({placeholders})
        ORDER BY bt.name
        """,
        tuple(post_ids),
    )
    by_post: dict[int, list[str]] = {}
    for row in tag_rows:
        by_post.setdefault(int(row["post_id"]), []).append(str(row["name"]))
    for row in rows:
        row["tags"] = by_post.get(int(row["id"]), [])


async def set_post_tags(
    conn: pymysql.Connection,
    *,
    post_id: int,
    course_id: int,
    tag_names: list[str],
) -> None:
    await execute(conn, "DELETE FROM blog_post_tags WHERE post_id = %s", (post_id,))
    if not tag_names:
        return

    tag_ids: list[int] = []
    for name in tag_names:
        slug = _tag_slug(name)
        existing = await fetch_one(
            conn,
            """
            SELECT id FROM blog_tags
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
            INSERT INTO blog_tags (course_id, name, slug)
            VALUES (%s, %s, %s)
            """,
            (course_id, name[:80], slug),
        )
        tag_ids.append(tag_id)

    for tag_id in tag_ids:
        await execute(
            conn,
            """
            INSERT IGNORE INTO blog_post_tags (post_id, tag_id)
            VALUES (%s, %s)
            """,
            (post_id, tag_id),
        )


async def list_posts(
    conn: pymysql.Connection,
    *,
    course_id: int | None = None,
    topic_id: int | None = None,
    limit: int = 30,
    after_id: int | None = None,
) -> list[dict[str, Any]]:
    clauses = ["bp.deleted_at IS NULL", "bps.code = 'published'"]
    params: list[Any] = []

    if course_id is not None:
        clauses.append("bp.course_id = %s")
        params.append(course_id)
    if topic_id is not None:
        clauses.append("bp.topic_id = %s")
        params.append(topic_id)
    if after_id is not None:
        clauses.append("bp.id < %s")
        params.append(after_id)

    params.append(limit)
    where = " AND ".join(clauses)

    rows = await fetch_all(
        conn,
        f"""
        SELECT
            bp.id, bp.title, bp.slug, bp.excerpt, bp.read_time_min, bp.is_pinned,
            bp.is_verified, bp.topic_id, bp.published_at, bp.created_at,
            c.code AS course_code,
            st.title AS topic_title,
            up.display_name AS author_name,
            ar.code AS author_role_code,
            cf.secure_url AS cover_image_url,
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
            COALESCE(SUM(CASE WHEN vd.value = -1 THEN 1 ELSE 0 END), 0) AS downvotes,
            (SELECT COUNT(*) FROM blog_comments bc
             WHERE bc.post_id = bp.id AND bc.deleted_at IS NULL) AS comment_count
        FROM blog_posts bp
        INNER JOIN courses c ON c.id = bp.course_id
        INNER JOIN blog_post_statuses bps ON bps.id = bp.status_id
        INNER JOIN user_profiles up ON up.user_id = bp.author_user_id
        INNER JOIN author_roles ar ON ar.id = bp.author_role_id
        LEFT JOIN syllabus_topics st ON st.id = bp.topic_id
        LEFT JOIN files cf ON cf.id = bp.cover_image_file_id AND cf.deleted_at IS NULL
        LEFT JOIN blog_post_votes bpv ON bpv.post_id = bp.id
        LEFT JOIN vote_directions vd ON vd.id = bpv.direction_id
        WHERE {where}
        GROUP BY bp.id, bp.title, bp.slug, bp.excerpt, bp.read_time_min, bp.is_pinned,
                 bp.is_verified, bp.topic_id, bp.published_at, bp.created_at,
                 c.code, st.title, up.display_name, ar.code, cf.secure_url
        ORDER BY bp.is_verified DESC, bp.is_pinned DESC, bp.published_at DESC, bp.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    await _attach_tags_to_posts(conn, rows)
    return rows


async def list_posts_by_author(
    conn: pymysql.Connection, author_user_id: int, *, limit: int = 12
) -> list[dict[str, Any]]:
    rows = await fetch_all(
        conn,
        """
        SELECT
            bp.id, bp.title, bp.slug, bp.excerpt, bp.read_time_min,
            bp.is_verified, bp.published_at, bp.created_at,
            c.code AS course_code,
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes
        FROM blog_posts bp
        INNER JOIN courses c ON c.id = bp.course_id
        INNER JOIN blog_post_statuses bps ON bps.id = bp.status_id
        LEFT JOIN blog_post_votes bpv ON bpv.post_id = bp.id
        LEFT JOIN vote_directions vd ON vd.id = bpv.direction_id
        WHERE bp.author_user_id = %s
          AND bp.deleted_at IS NULL
          AND bps.code = 'published'
        GROUP BY bp.id, bp.title, bp.slug, bp.excerpt, bp.read_time_min,
                 bp.is_verified, bp.published_at, bp.created_at, c.code
        ORDER BY bp.published_at DESC, bp.id DESC
        LIMIT %s
        """,
        (author_user_id, limit),
    )
    return list(rows)


async def _post_vote_counts(
    conn: pymysql.Connection, post_id: int, *, viewer_user_id: int | None = None
) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """
        SELECT
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
            COALESCE(SUM(CASE WHEN vd.value = -1 THEN 1 ELSE 0 END), 0) AS downvotes
        FROM blog_post_votes bpv
        INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
        WHERE bpv.post_id = %s
        """,
        (post_id,),
    )
    counts = {
        "upvotes": int(row["upvotes"] or 0) if row else 0,
        "downvotes": int(row["downvotes"] or 0) if row else 0,
        "viewer_vote": None,
    }
    if viewer_user_id is not None:
        viewer = await fetch_one(
            conn,
            """
            SELECT vd.code AS viewer_vote
            FROM blog_post_votes bpv
            INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
            WHERE bpv.post_id = %s AND bpv.voter_user_id = %s
            """,
            (post_id, viewer_user_id),
        )
        if viewer:
            counts["viewer_vote"] = viewer["viewer_vote"]
    return counts


async def get_post(
    conn: pymysql.Connection, post_id: int, *, viewer_user_id: int | None = None
) -> dict[str, Any] | None:
    viewer_select = ""
    params: tuple[Any, ...] = (post_id,)
    if viewer_user_id is not None:
        viewer_select = """,
            (SELECT vd_viewer.code
             FROM blog_post_votes bpv_viewer
             INNER JOIN vote_directions vd_viewer ON vd_viewer.id = bpv_viewer.direction_id
             WHERE bpv_viewer.post_id = bp.id AND bpv_viewer.voter_user_id = %s
             LIMIT 1) AS viewer_vote"""
        params = (viewer_user_id, post_id)

    post = await fetch_one(
        conn,
        f"""
        SELECT
            bp.id, bp.title, bp.slug, bp.excerpt, bp.body_html, bp.read_time_min,
            bp.is_pinned, bp.is_verified, bp.topic_id, bp.cover_image_file_id,
            bp.published_at, bp.created_at,
            c.code AS course_code, c.id AS course_id,
            st.title AS topic_title,
            up.display_name AS author_name,
            ar.code AS author_role_code,
            u.id AS author_user_id,
            cf.secure_url AS cover_image_url,
            COALESCE((
                SELECT SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END)
                FROM blog_post_votes bpv
                INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
                WHERE bpv.post_id = bp.id
            ), 0) AS upvotes,
            COALESCE((
                SELECT SUM(CASE WHEN vd.value = -1 THEN 1 ELSE 0 END)
                FROM blog_post_votes bpv
                INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
                WHERE bpv.post_id = bp.id
            ), 0) AS downvotes,
            (SELECT COUNT(*) FROM blog_comments bc
             WHERE bc.post_id = bp.id AND bc.deleted_at IS NULL) AS comment_count
            {viewer_select}
        FROM blog_posts bp
        INNER JOIN courses c ON c.id = bp.course_id
        LEFT JOIN syllabus_topics st ON st.id = bp.topic_id
        INNER JOIN user_profiles up ON up.user_id = bp.author_user_id
        INNER JOIN author_roles ar ON ar.id = bp.author_role_id
        INNER JOIN users u ON u.id = bp.author_user_id
        LEFT JOIN files cf ON cf.id = bp.cover_image_file_id AND cf.deleted_at IS NULL
        WHERE bp.id = %s AND bp.deleted_at IS NULL
        """,
        params,
    )
    if post:
        await _attach_tags_to_posts(conn, [post])
    return post


async def list_posts_admin(
    conn: pymysql.Connection,
    *,
    course_id: int | None = None,
    topic_id: int | None = None,
    q: str | None = None,
    verified_only: bool = False,
    moderation_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = ["bp.deleted_at IS NULL", "bps.code = 'published'"]
    params: list[Any] = []

    if course_id is not None:
        clauses.append("bp.course_id = %s")
        params.append(course_id)
    if topic_id is not None:
        clauses.append("bp.topic_id = %s")
        params.append(topic_id)
    if moderation_only:
        clauses.append("bp.is_verified = 1")
        clauses.append("ar.code IN ('student', 'faculty')")
    elif verified_only:
        clauses.append("bp.is_verified = 1")
    if q:
        clauses.append("(bp.title LIKE %s OR bp.excerpt LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])

    params.append(limit)
    where = " AND ".join(clauses)

    rows = await fetch_all(
        conn,
        f"""
        SELECT
            bp.id, bp.title, bp.slug, bp.excerpt, bp.body_html, bp.read_time_min,
            bp.is_pinned, bp.is_verified, bp.topic_id, bp.cover_image_file_id,
            bp.published_at, bp.created_at,
            c.code AS course_code,
            st.title AS topic_title,
            up.display_name AS author_name,
            ar.code AS author_role_code,
            cf.secure_url AS cover_image_url,
            COALESCE(SUM(CASE WHEN vd.value = 1 THEN 1 ELSE 0 END), 0) AS upvotes,
            COALESCE(SUM(CASE WHEN vd.value = -1 THEN 1 ELSE 0 END), 0) AS downvotes,
            (SELECT COUNT(*) FROM blog_comments bc
             WHERE bc.post_id = bp.id AND bc.deleted_at IS NULL) AS comment_count
        FROM blog_posts bp
        INNER JOIN courses c ON c.id = bp.course_id
        INNER JOIN blog_post_statuses bps ON bps.id = bp.status_id
        INNER JOIN user_profiles up ON up.user_id = bp.author_user_id
        INNER JOIN author_roles ar ON ar.id = bp.author_role_id
        LEFT JOIN syllabus_topics st ON st.id = bp.topic_id
        LEFT JOIN files cf ON cf.id = bp.cover_image_file_id AND cf.deleted_at IS NULL
        LEFT JOIN blog_post_votes bpv ON bpv.post_id = bp.id
        LEFT JOIN vote_directions vd ON vd.id = bpv.direction_id
        WHERE {where}
        GROUP BY bp.id, bp.title, bp.slug, bp.excerpt, bp.body_html, bp.read_time_min,
                 bp.is_pinned, bp.is_verified, bp.topic_id, bp.cover_image_file_id,
                 bp.published_at, bp.created_at,
                 c.code, st.title, up.display_name, ar.code, cf.secure_url
        ORDER BY bp.published_at DESC, bp.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    await _attach_tags_to_posts(conn, rows)
    return rows


async def create_post(
    conn: pymysql.Connection,
    *,
    course_id: int,
    topic_id: int | None,
    author_user_id: int,
    author_role_code: str,
    title: str,
    excerpt: str,
    body_html: str,
    read_time_min: int = 5,
    is_verified: bool = False,
    verified_by_user_id: int | None = None,
    cover_image_file_id: int | None = None,
) -> int:
    status = await fetch_one(
        conn, "SELECT id FROM blog_post_statuses WHERE code = 'published' LIMIT 1"
    )
    role = await fetch_one(
        conn, "SELECT id FROM author_roles WHERE code = %s", (author_role_code,)
    )
    if not status or not role:
        raise ValueError("Missing blog status or author role lookup")

    slug = await _unique_slug(conn, course_id, title, topic_id)
    verified_at = "UTC_TIMESTAMP(3)" if is_verified else "NULL"
    return await execute_returning_id(
        conn,
        f"""
        INSERT INTO blog_posts (
            course_id, topic_id, author_user_id, author_role_id, status_id,
            title, slug, excerpt, body_html, cover_image_file_id, read_time_min,
            is_verified, verified_by_user_id, verified_at, published_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, {verified_at}, UTC_TIMESTAMP(3))
        """,
        (
            course_id,
            topic_id,
            author_user_id,
            role["id"],
            status["id"],
            title,
            slug,
            excerpt,
            body_html,
            cover_image_file_id,
            read_time_min,
            int(is_verified),
            verified_by_user_id if is_verified else None,
        ),
    )


async def verify_post(
    conn: pymysql.Connection,
    post_id: int,
    *,
    verifier_user_id: int,
) -> bool:
    post = await fetch_one(
        conn,
        """
        SELECT bp.id, ar.code AS author_role_code
        FROM blog_posts bp
        INNER JOIN author_roles ar ON ar.id = bp.author_role_id
        WHERE bp.id = %s AND bp.deleted_at IS NULL
        """,
        (post_id,),
    )
    if not post:
        return False
    if post["author_role_code"] != "student":
        return False

    count = await execute(
        conn,
        """
        UPDATE blog_posts
        SET is_verified = 1,
            verified_by_user_id = %s,
            verified_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND deleted_at IS NULL
        """,
        (verifier_user_id, post_id),
    )
    return count > 0


async def list_comments(conn: pymysql.Connection, post_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            bc.id, bc.parent_comment_id, bc.body, bc.created_at,
            up.display_name AS author_name,
            u.id AS author_user_id,
            r.code AS author_role_code
        FROM blog_comments bc
        INNER JOIN users u ON u.id = bc.author_user_id
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_profiles up ON up.user_id = bc.author_user_id
        WHERE bc.post_id = %s AND bc.deleted_at IS NULL
        ORDER BY bc.created_at ASC
        """,
        (post_id,),
    )


async def add_comment(
    conn: pymysql.Connection,
    *,
    post_id: int,
    author_user_id: int,
    body: str,
    parent_comment_id: int | None = None,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO blog_comments (post_id, parent_comment_id, author_user_id, body)
        VALUES (%s, %s, %s, %s)
        """,
        (post_id, parent_comment_id, author_user_id, body),
    )


async def update_post(
    conn: pymysql.Connection,
    post_id: int,
    *,
    author_user_id: int | None = None,
    title: str | None = None,
    excerpt: str | None = None,
    body_html: str | None = None,
    read_time_min: int | None = None,
    cover_image_file_id: int | None = ...,  # type: ignore[assignment]
    is_admin: bool = False,
) -> bool:
    post = await fetch_one(
        conn, "SELECT author_user_id FROM blog_posts WHERE id = %s AND deleted_at IS NULL", (post_id,)
    )
    if not post:
        return False
    if not is_admin and post["author_user_id"] != author_user_id:
        return False

    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = %s")
        params.append(title)
        fields.append("slug = %s")
        params.append(_slugify(title))
    if excerpt is not None:
        fields.append("excerpt = %s")
        params.append(excerpt)
    if body_html is not None:
        fields.append("body_html = %s")
        params.append(body_html)
    if read_time_min is not None:
        fields.append("read_time_min = %s")
        params.append(read_time_min)
    if cover_image_file_id is not ...:
        fields.append("cover_image_file_id = %s")
        params.append(cover_image_file_id)
    if not fields:
        return True

    params.append(post_id)
    count = await execute(
        conn, f"UPDATE blog_posts SET {', '.join(fields)} WHERE id = %s", tuple(params)
    )
    return count > 0


async def delete_comment(conn: pymysql.Connection, comment_id: int) -> bool:
    count = await execute(
        conn,
        """
        UPDATE blog_comments
        SET deleted_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND deleted_at IS NULL
        """,
        (comment_id,),
    )
    return count > 0


async def delete_post(
    conn: pymysql.Connection, post_id: int, *, author_user_id: int | None = None, is_admin: bool = False
) -> bool:
    post = await fetch_one(
        conn, "SELECT author_user_id FROM blog_posts WHERE id = %s AND deleted_at IS NULL", (post_id,)
    )
    if not post:
        return False
    if not is_admin and post["author_user_id"] != author_user_id:
        return False
    count = await execute(
        conn,
        "UPDATE blog_posts SET deleted_at = UTC_TIMESTAMP(3) WHERE id = %s",
        (post_id,),
    )
    return count > 0


async def set_pinned(conn: pymysql.Connection, post_id: int, pinned: bool) -> bool:
    count = await execute(
        conn,
        "UPDATE blog_posts SET is_pinned = %s WHERE id = %s AND deleted_at IS NULL",
        (int(pinned), post_id),
    )
    return count > 0


async def vote_post(
    conn: pymysql.Connection, post_id: int, voter_user_id: int, direction_code: str
) -> tuple[int | None, dict[str, Any]]:
    direction = await fetch_one(
        conn, "SELECT id FROM vote_directions WHERE code = %s", (direction_code,)
    )
    if not direction:
        return None, await _post_vote_counts(conn, post_id, viewer_user_id=voter_user_id)

    existing = await fetch_one(
        conn,
        """
        SELECT vd.code AS direction_code
        FROM blog_post_votes bpv
        INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
        WHERE bpv.post_id = %s AND bpv.voter_user_id = %s
        """,
        (post_id, voter_user_id),
    )
    if existing and existing["direction_code"] == direction_code:
        await execute(
            conn,
            "DELETE FROM blog_post_votes WHERE post_id = %s AND voter_user_id = %s",
            (post_id, voter_user_id),
        )
    else:
        await execute(
            conn,
            """
            INSERT INTO blog_post_votes (post_id, voter_user_id, direction_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE direction_id = VALUES(direction_id)
            """,
            (post_id, voter_user_id, direction["id"]),
        )

    post = await fetch_one(
        conn, "SELECT author_user_id FROM blog_posts WHERE id = %s", (post_id,)
    )
    author_id = post["author_user_id"] if post else None
    counts = await _post_vote_counts(conn, post_id, viewer_user_id=voter_user_id)
    return author_id, counts
