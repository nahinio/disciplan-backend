"""Raw SQL repository — authentication & OTP."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncmy

from app.config import get_settings
from app.db.session import execute, execute_returning_id, fetch_one
from app.utils.security import hash_otp, hash_password, hash_token


async def get_user_by_email(conn: asyncmy.Connection, email: str) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT u.id, u.email, u.password_hash, u.email_verified,
               r.code AS role_code, us.code AS status_code
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_statuses us ON us.id = u.status_id
        WHERE u.email = %s
        """,
        (email.lower(),),
    )


async def get_role_id(conn: asyncmy.Connection, role_code: str) -> int | None:
    row = await fetch_one(conn, "SELECT id FROM roles WHERE code = %s", (role_code,))
    return row["id"] if row else None


async def get_status_id(conn: asyncmy.Connection, status_code: str) -> int | None:
    row = await fetch_one(conn, "SELECT id FROM user_statuses WHERE code = %s", (status_code,))
    return row["id"] if row else None


async def create_otp(conn: asyncmy.Connection, email: str, code: str) -> None:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)
    await execute(
        conn,
        """
        INSERT INTO otp_verifications (email, code_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (email.lower(), hash_otp(code), expires),
    )


async def verify_otp(conn: asyncmy.Connection, email: str, code: str) -> bool:
    row = await fetch_one(
        conn,
        """
        SELECT id FROM otp_verifications
        WHERE email = %s
          AND code_hash = %s
          AND consumed_at IS NULL
          AND expires_at > UTC_TIMESTAMP(3)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email.lower(), hash_otp(code)),
    )
    if row is None:
        return False

    await execute(
        conn,
        "UPDATE otp_verifications SET consumed_at = UTC_TIMESTAMP(3) WHERE id = %s",
        (row["id"],),
    )
    return True


async def create_user(
    conn: asyncmy.Connection,
    *,
    email: str,
    password: str,
    role_code: str,
    display_name: str,
    department_id: int | None,
    status_code: str = "active",
) -> int:
    role_id = await get_role_id(conn, role_code)
    status_id = await get_status_id(conn, status_code)
    if role_id is None or status_id is None:
        raise ValueError("Invalid role or status")

    user_id = await execute_returning_id(
        conn,
        """
        INSERT INTO users (email, password_hash, role_id, status_id, email_verified)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (email.lower(), hash_password(password), role_id, status_id),
    )

    await execute(
        conn,
        """
        INSERT INTO user_profiles (user_id, display_name, department_id)
        VALUES (%s, %s, %s)
        """,
        (user_id, display_name, department_id),
    )

    await execute(
        conn,
        "INSERT INTO user_preferences (user_id) VALUES (%s)",
        (user_id,),
    )

    tier_row = await fetch_one(
        conn,
        "SELECT id FROM gamification_tiers WHERE code = 'bronze' LIMIT 1",
    )
    tier_id = tier_row["id"] if tier_row else 1

    await execute(
        conn,
        "INSERT INTO user_gamification (user_id, tier_id, total_points) VALUES (%s, %s, 0)",
        (user_id, tier_id),
    )

    return user_id


async def store_refresh_token(conn: asyncmy.Connection, user_id: int, token: str, expires_at: datetime) -> None:
    await execute(
        conn,
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        """,
        (user_id, hash_token(token), expires_at),
    )


async def revoke_refresh_token(conn: asyncmy.Connection, token: str) -> None:
    await execute(
        conn,
        "UPDATE refresh_tokens SET revoked_at = UTC_TIMESTAMP(3) WHERE token_hash = %s",
        (hash_token(token),),
    )


async def get_refresh_token_user(conn: asyncmy.Connection, token: str) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT rt.user_id, u.email, r.code AS role_code
        FROM refresh_tokens rt
        INNER JOIN users u ON u.id = rt.user_id
        INNER JOIN roles r ON r.id = u.role_id
        WHERE rt.token_hash = %s
          AND rt.revoked_at IS NULL
          AND rt.expires_at > UTC_TIMESTAMP(3)
        """,
        (hash_token(token),),
    )


async def touch_last_login(conn: asyncmy.Connection, user_id: int) -> None:
    await execute(conn, "UPDATE users SET last_login_at = UTC_TIMESTAMP(3) WHERE id = %s", (user_id,))
