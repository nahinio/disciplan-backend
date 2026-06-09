"""Raw SQL repository — file metadata (Cloudinary binaries)."""

from __future__ import annotations

from typing import Any

import asyncmy

from app.db.session import execute_returning_id, fetch_one


async def get_storage_provider_id(conn: asyncmy.Connection, code: str = "cloudinary") -> int:
    row = await fetch_one(
        conn, "SELECT id FROM file_storage_providers WHERE code = %s", (code,)
    )
    if row is None:
        raise ValueError(f"Unknown storage provider: {code}")
    return row["id"]


async def insert_file(
    conn: asyncmy.Connection,
    *,
    uploaded_by_user_id: int,
    storage_key: str,
    secure_url: str,
    original_filename: str,
    mime_type: str,
    size_bytes: int,
    checksum_sha256: str | None = None,
    width_px: int | None = None,
    height_px: int | None = None,
) -> int:
    provider_id = await get_storage_provider_id(conn)

    return await execute_returning_id(
        conn,
        """
        INSERT INTO files (
            storage_provider_id, storage_key, secure_url, original_filename,
            mime_type, size_bytes, checksum_sha256, width_px, height_px,
            uploaded_by_user_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            provider_id,
            storage_key,
            secure_url,
            original_filename,
            mime_type,
            size_bytes,
            checksum_sha256,
            width_px,
            height_px,
            uploaded_by_user_id,
        ),
    )


async def get_file_by_id(conn: asyncmy.Connection, file_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT f.id, f.storage_key, f.secure_url, f.original_filename,
               f.mime_type, f.size_bytes, f.created_at,
               fsp.code AS storage_provider_code
        FROM files f
        INNER JOIN file_storage_providers fsp ON fsp.id = f.storage_provider_id
        WHERE f.id = %s AND f.deleted_at IS NULL
        """,
        (file_id,),
    )
