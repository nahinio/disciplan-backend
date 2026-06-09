"""Faculty verification requests — self-signup queue for admin review."""

from __future__ import annotations

from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def create_request(
    conn: pymysql.Connection,
    *,
    user_id: int,
    email: str,
    display_name: str,
    message: str | None = None,
) -> int:
    return await execute_returning_id(
        conn,
        """
        INSERT INTO faculty_verification_requests (user_id, email, display_name, status, message)
        VALUES (%s, %s, %s, 'pending', %s)
        """,
        (user_id, email.lower(), display_name.strip(), message),
    )


async def list_requests(
    conn: pymysql.Connection, *, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        return await fetch_all(
            conn,
            """
            SELECT
                fvr.id, fvr.user_id, fvr.email, fvr.display_name, fvr.status,
                fvr.message, fvr.created_at, fvr.reviewed_at,
                rev.display_name AS reviewed_by_name
            FROM faculty_verification_requests fvr
            LEFT JOIN user_profiles rev ON rev.user_id = fvr.reviewed_by_user_id
            WHERE fvr.status = %s
            ORDER BY fvr.created_at DESC
            """,
            (status,),
        )
    return await fetch_all(
        conn,
        """
        SELECT
            fvr.id, fvr.user_id, fvr.email, fvr.display_name, fvr.status,
            fvr.message, fvr.created_at, fvr.reviewed_at,
            rev.display_name AS reviewed_by_name
        FROM faculty_verification_requests fvr
        LEFT JOIN user_profiles rev ON rev.user_id = fvr.reviewed_by_user_id
        ORDER BY fvr.created_at DESC
        """,
    )


async def get_request(conn: pymysql.Connection, request_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, user_id, email, display_name, status, message, created_at
        FROM faculty_verification_requests
        WHERE id = %s
        """,
        (request_id,),
    )


async def get_pending_by_user(conn: pymysql.Connection, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT id, status FROM faculty_verification_requests
        WHERE user_id = %s AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )


async def approve_request(
    conn: pymysql.Connection, *, request_id: int, reviewer_id: int
) -> dict[str, Any] | None:
    req = await get_request(conn, request_id)
    if not req or req["status"] != "pending":
        return None

    active = await fetch_one(conn, "SELECT id FROM user_statuses WHERE code = 'active' LIMIT 1")
    if not active:
        raise ValueError("Missing active status")

    await execute(
        conn,
        "UPDATE users SET status_id = %s WHERE id = %s",
        (active["id"], req["user_id"]),
    )
    await execute(
        conn,
        """
        UPDATE faculty_verification_requests
        SET status = 'approved', reviewed_by_user_id = %s, reviewed_at = UTC_TIMESTAMP(3)
        WHERE id = %s
        """,
        (reviewer_id, request_id),
    )
    return req


async def reject_request(
    conn: pymysql.Connection, *, request_id: int, reviewer_id: int
) -> dict[str, Any] | None:
    req = await get_request(conn, request_id)
    if not req or req["status"] != "pending":
        return None

    suspended = await fetch_one(
        conn, "SELECT id FROM user_statuses WHERE code = 'suspended' LIMIT 1"
    )
    if not suspended:
        raise ValueError("Missing suspended status")

    await execute(
        conn,
        "UPDATE users SET status_id = %s WHERE id = %s",
        (suspended["id"], req["user_id"]),
    )
    await execute(
        conn,
        """
        UPDATE faculty_verification_requests
        SET status = 'rejected', reviewed_by_user_id = %s, reviewed_at = UTC_TIMESTAMP(3)
        WHERE id = %s
        """,
        (reviewer_id, request_id),
    )
    return req
