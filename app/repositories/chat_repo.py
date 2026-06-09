"""Raw SQL repository — DB-backed chat (poll delivery, no WebSocket)."""

from __future__ import annotations

from typing import Any

import asyncmy

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def list_user_groups(conn: asyncmy.Connection, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            cg.id,
            cg.name,
            cg.team_id,
            cgt.code AS group_type_code,
            c.code AS course_code,
            s.section_label,
            lm.last_message_id,
            lm.last_message_preview,
            lm.last_message_at,
            COALESCE(uc.unread_count, 0) AS unread_count
        FROM chat_group_members cgm
        INNER JOIN chat_groups cg ON cg.id = cgm.group_id AND cg.is_active = 1
        INNER JOIN chat_group_types cgt ON cgt.id = cg.group_type_id
        LEFT JOIN sections s ON s.id = cg.section_id
        LEFT JOIN courses c ON c.id = s.course_id
        LEFT JOIN v_chat_group_last_messages lm ON lm.group_id = cg.id
        LEFT JOIN v_chat_group_unread_counts uc
            ON uc.group_id = cg.id AND uc.user_id = cgm.user_id
        WHERE cgm.user_id = %s AND cgm.left_at IS NULL
        ORDER BY lm.last_message_at DESC, cg.name ASC
        """,
        (user_id,),
    )


async def get_messages_since(
    conn: asyncmy.Connection,
    group_id: int,
    user_id: int,
    *,
    after_id: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Keyset pagination — efficient for polling."""
    membership = await fetch_one(
        conn,
        """
        SELECT 1 FROM chat_group_members
        WHERE group_id = %s AND user_id = %s AND left_at IS NULL
        """,
        (group_id, user_id),
    )
    if membership is None:
        return []

    return await fetch_all(
        conn,
        """
        SELECT
            cm.id,
            cm.sender_user_id,
            up.display_name AS sender_name,
            cm.body,
            cm.created_at,
            cm.edited_at,
            EXISTS (
                SELECT 1 FROM chat_message_reads cmr
                WHERE cmr.message_id = cm.id AND cmr.user_id = %s
            ) AS is_read_by_me
        FROM chat_messages cm
        INNER JOIN user_profiles up ON up.user_id = cm.sender_user_id
        WHERE cm.group_id = %s
          AND cm.deleted_at IS NULL
          AND cm.id > %s
        ORDER BY cm.id ASC
        LIMIT %s
        """,
        (user_id, group_id, after_id, limit),
    )


async def send_message(
    conn: asyncmy.Connection,
    *,
    group_id: int,
    sender_user_id: int,
    body: str,
) -> int:
    member = await fetch_one(
        conn,
        """
        SELECT 1 FROM chat_group_members
        WHERE group_id = %s AND user_id = %s AND left_at IS NULL
        """,
        (group_id, sender_user_id),
    )
    if member is None:
        raise PermissionError("Not a member of this group")

    return await execute_returning_id(
        conn,
        """
        INSERT INTO chat_messages (group_id, sender_user_id, body)
        VALUES (%s, %s, %s)
        """,
        (group_id, sender_user_id, body),
    )


async def get_message_by_id(
    conn: asyncmy.Connection, message_id: int, reader_user_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT
            cm.id,
            cm.sender_user_id,
            up.display_name AS sender_name,
            cm.body,
            cm.created_at,
            cm.edited_at,
            EXISTS (
                SELECT 1 FROM chat_message_reads cmr
                WHERE cmr.message_id = cm.id AND cmr.user_id = %s
            ) AS is_read_by_me
        FROM chat_messages cm
        INNER JOIN user_profiles up ON up.user_id = cm.sender_user_id
        WHERE cm.id = %s AND cm.deleted_at IS NULL
        """,
        (reader_user_id, message_id),
    )


async def mark_messages_read(
    conn: asyncmy.Connection,
    group_id: int,
    user_id: int,
    up_to_message_id: int,
) -> int:
    """Mark all messages up to cursor as read — batch INSERT IGNORE."""
    return await execute(
        conn,
        """
        INSERT IGNORE INTO chat_message_reads (message_id, user_id)
        SELECT cm.id, %s
        FROM chat_messages cm
        WHERE cm.group_id = %s
          AND cm.id <= %s
          AND cm.sender_user_id <> %s
          AND cm.deleted_at IS NULL
        """,
        (user_id, group_id, up_to_message_id, user_id),
    )


async def add_group_member(
    conn: asyncmy.Connection, group_id: int, user_id: int
) -> None:
    await execute(
        conn,
        "INSERT IGNORE INTO chat_group_members (group_id, user_id) VALUES (%s, %s)",
        (group_id, user_id),
    )


async def get_section_group(
    conn: asyncmy.Connection, section_id: int
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id FROM chat_groups
        WHERE section_id = %s AND is_active = 1
        LIMIT 1
        """,
        (section_id,),
    )


async def ensure_section_chat_member(
    conn: asyncmy.Connection,
    *,
    section_id: int,
    user_id: int,
    group_name: str,
    created_by_user_id: int,
) -> int:
    """Add user to section chat group, creating the group if needed."""
    existing = await get_section_group(conn, section_id)
    if existing:
        await add_group_member(conn, existing["id"], user_id)
        return existing["id"]

    faculty_rows = await fetch_all(
        conn,
        "SELECT faculty_user_id FROM section_faculty WHERE section_id = %s",
        (section_id,),
    )
    member_ids = list({user_id, *(r["faculty_user_id"] for r in faculty_rows)})
    return await create_section_group(
        conn,
        section_id=section_id,
        name=group_name,
        created_by_user_id=created_by_user_id,
        member_user_ids=member_ids,
    )


async def create_section_group(
    conn: asyncmy.Connection,
    *,
    section_id: int,
    name: str,
    created_by_user_id: int,
    member_user_ids: list[int],
) -> int:
    type_row = await fetch_one(
        conn, "SELECT id FROM chat_group_types WHERE code = 'section' LIMIT 1"
    )
    if type_row is None:
        raise ValueError("Missing chat group type")

    group_id = await execute_returning_id(
        conn,
        """
        INSERT INTO chat_groups (section_id, group_type_id, name, created_by_user_id)
        VALUES (%s, %s, %s, %s)
        """,
        (section_id, type_row["id"], name, created_by_user_id),
    )

    all_members = set(member_user_ids) | {created_by_user_id}
    for uid in all_members:
        await execute(
            conn,
            "INSERT INTO chat_group_members (group_id, user_id) VALUES (%s, %s)",
            (group_id, uid),
        )

    return group_id


async def create_team_group(
    conn: asyncmy.Connection,
    *,
    team_id: int,
    name: str,
    created_by_user_id: int,
    member_user_ids: list[int],
) -> int:
    type_row = await fetch_one(
        conn, "SELECT id FROM chat_group_types WHERE code = 'project' LIMIT 1"
    )
    if type_row is None:
        raise ValueError("Missing chat group type")

    existing = await fetch_one(
        conn,
        "SELECT id FROM chat_groups WHERE team_id = %s AND is_active = 1 LIMIT 1",
        (team_id,),
    )
    if existing:
        return existing["id"]

    group_id = await execute_returning_id(
        conn,
        """
        INSERT INTO chat_groups (team_id, group_type_id, name, created_by_user_id)
        VALUES (%s, %s, %s, %s)
        """,
        (team_id, type_row["id"], name, created_by_user_id),
    )
    all_members = set(member_user_ids) | {created_by_user_id}
    for uid in all_members:
        await execute(
            conn,
            "INSERT IGNORE INTO chat_group_members (group_id, user_id) VALUES (%s, %s)",
            (group_id, uid),
        )
    return group_id
