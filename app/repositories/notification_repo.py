"""Raw SQL repository — poll-based notifications."""

from __future__ import annotations

from typing import Any

import asyncmy

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def get_unread_count(conn: asyncmy.Connection, user_id: int) -> int:
    row = await fetch_one(
        conn,
        "SELECT unread_count FROM v_user_unread_notification_counts WHERE user_id = %s",
        (user_id,),
    )
    return int(row["unread_count"]) if row else 0


async def list_notifications(
    conn: asyncmy.Connection,
    user_id: int,
    *,
    only_unread: bool = False,
    limit: int = 20,
    after_id: int | None = None,
) -> list[dict[str, Any]]:
    clauses = ["recipient_user_id = %s"]
    params: list[Any] = [user_id]

    if only_unread:
        clauses.append("is_read = 0")
    if after_id is not None:
        clauses.append("id < %s")
        params.append(after_id)

    params.append(limit)
    where = " AND ".join(clauses)

    return await fetch_all(
        conn,
        f"""
        SELECT
            n.id,
            nt.code AS type_code,
            n.title,
            n.body_preview,
            ret.code AS reference_type_code,
            n.reference_id,
            n.action_path,
            n.is_read,
            n.read_at,
            n.created_at
        FROM notifications n
        INNER JOIN notification_types nt ON nt.id = n.type_id
        LEFT JOIN reference_entity_types ret ON ret.id = n.reference_type_id
        WHERE {where}
        ORDER BY n.id DESC
        LIMIT %s
        """,
        tuple(params),
    )


async def mark_read(conn: asyncmy.Connection, user_id: int, notification_id: int) -> bool:
    count = await execute(
        conn,
        """
        UPDATE notifications
        SET is_read = 1, read_at = UTC_TIMESTAMP(3)
        WHERE id = %s AND recipient_user_id = %s AND is_read = 0
        """,
        (notification_id, user_id),
    )
    return count > 0


async def mark_all_read(conn: asyncmy.Connection, user_id: int) -> int:
    return await execute(
        conn,
        """
        UPDATE notifications
        SET is_read = 1, read_at = UTC_TIMESTAMP(3)
        WHERE recipient_user_id = %s AND is_read = 0
        """,
        (user_id,),
    )


async def create_notifications_for_group_message(
    conn: asyncmy.Connection,
    *,
    group_id: int,
    message_id: int,
    sender_user_id: int,
    body_preview: str,
    action_path: str,
) -> int:
    """Notify all active group members except sender — complex multi-row INSERT."""
    type_row = await fetch_one(
        conn, "SELECT id FROM notification_types WHERE code = 'new_message' LIMIT 1"
    )
    ref_row = await fetch_one(
        conn, "SELECT id FROM reference_entity_types WHERE code = 'message' LIMIT 1"
    )
    if type_row is None or ref_row is None:
        raise ValueError("Missing notification lookup rows")

    group_row = await fetch_one(
        conn,
        """
        SELECT cg.name AS group_name, c.code AS course_code
        FROM chat_groups cg
        LEFT JOIN sections s ON s.id = cg.section_id
        LEFT JOIN courses c ON c.id = s.course_id
        WHERE cg.id = %s
        """,
        (group_id,),
    )
    title = f"New message in {group_row['group_name']}" if group_row else "New chat message"

    return await execute(
        conn,
        f"""
        INSERT INTO notifications (
            recipient_user_id, type_id, title, body_preview,
            reference_type_id, reference_id, action_path
        )
        SELECT
            cgm.user_id,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        FROM chat_group_members cgm
        WHERE cgm.group_id = %s
          AND cgm.left_at IS NULL
          AND cgm.user_id <> %s
        """,
        (
            type_row["id"],
            title,
            body_preview[:300],
            ref_row["id"],
            message_id,
            action_path,
            group_id,
            sender_user_id,
        ),
    )


async def create_notification(
    conn: asyncmy.Connection,
    *,
    recipient_user_id: int,
    type_code: str,
    title: str,
    body_preview: str | None = None,
    reference_type_code: str | None = None,
    reference_id: int | None = None,
    action_path: str | None = None,
) -> int:
    type_row = await fetch_one(
        conn, "SELECT id FROM notification_types WHERE code = %s", (type_code,)
    )
    ref_type_id = None
    if reference_type_code:
        ref_row = await fetch_one(
            conn, "SELECT id FROM reference_entity_types WHERE code = %s", (reference_type_code,)
        )
        ref_type_id = ref_row["id"] if ref_row else None

    if type_row is None:
        raise ValueError(f"Unknown notification type: {type_code}")

    return await execute_returning_id(
        conn,
        """
        INSERT INTO notifications (
            recipient_user_id, type_id, title, body_preview,
            reference_type_id, reference_id, action_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            recipient_user_id,
            type_row["id"],
            title,
            body_preview,
            ref_type_id,
            reference_id,
            action_path,
        ),
    )
