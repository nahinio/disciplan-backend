"""Raw SQL — admin faculty roster for automatic role assignment on signup."""

from __future__ import annotations

from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def list_roster(conn: pymysql.Connection) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT
            fr.id,
            fr.email,
            fr.display_name,
            fr.status,
            fr.claimed_user_id,
            fr.claimed_at,
            fr.created_at,
            inv.display_name AS invited_by_name
        FROM faculty_roster fr
        LEFT JOIN user_profiles inv ON inv.user_id = fr.invited_by_user_id
        ORDER BY fr.status ASC, fr.created_at DESC
        """,
    )


async def get_pending_by_email(conn: pymysql.Connection, email: str) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, email, display_name, status
        FROM faculty_roster
        WHERE LOWER(email) = LOWER(%s) AND status = 'pending'
        LIMIT 1
        """,
        (email,),
    )


async def add_roster_entry(
    conn: pymysql.Connection,
    *,
    email: str,
    display_name: str,
    invited_by_user_id: int | None,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO faculty_roster (email, display_name, invited_by_user_id, status)
        VALUES (%s, %s, %s, 'pending')
        """,
        (email.lower(), display_name.strip(), invited_by_user_id),
    )


async def delete_pending(conn: pymysql.Connection, roster_id: int) -> bool:
    row = await fetch_one(
        conn,
        "SELECT id FROM faculty_roster WHERE id = %s AND status = 'pending'",
        (roster_id,),
    )
    if not row:
        return False
    await execute(conn, "DELETE FROM faculty_roster WHERE id = %s", (roster_id,))
    return True


async def ensure_claimed(
    conn: pymysql.Connection,
    *,
    email: str,
    display_name: str,
    user_id: int,
    invited_by_user_id: int | None = None,
) -> None:
    await execute(
        conn,
        """
        INSERT INTO faculty_roster (
            email, display_name, invited_by_user_id, status, claimed_user_id, claimed_at
        ) VALUES (%s, %s, %s, 'claimed', %s, UTC_TIMESTAMP(3))
        ON DUPLICATE KEY UPDATE
            display_name = VALUES(display_name),
            status = 'claimed',
            claimed_user_id = VALUES(claimed_user_id),
            claimed_at = UTC_TIMESTAMP(3)
        """,
        (email.lower(), display_name.strip(), invited_by_user_id, user_id),
    )


async def claim_roster_entry(
    conn: pymysql.Connection, *, email: str, user_id: int
) -> None:
    await execute(
        conn,
        """
        UPDATE faculty_roster
        SET status = 'claimed',
            claimed_user_id = %s,
            claimed_at = UTC_TIMESTAMP(3)
        WHERE LOWER(email) = LOWER(%s) AND status = 'pending'
        """,
        (user_id, email),
    )
