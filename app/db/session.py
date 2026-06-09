"""Async wrappers around sync PyMySQL pool."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pymysql

from app.db.pool import acquire, release


@asynccontextmanager
async def get_connection() -> AsyncIterator[pymysql.Connection]:
    conn = await asyncio.to_thread(acquire)
    try:
        yield conn
    finally:
        await asyncio.to_thread(release, conn)


@asynccontextmanager
async def transaction() -> AsyncIterator[pymysql.Connection]:
    async with get_connection() as conn:
        try:
            await asyncio.to_thread(conn.begin)
            yield conn
            await asyncio.to_thread(conn.commit)
        except Exception:
            try:
                await asyncio.to_thread(conn.rollback)
            except Exception:
                pass
            raise


async def fetch_one(
    conn: pymysql.Connection, sql: str, params: tuple[Any, ...] | None = None
) -> dict[str, Any] | None:
    def _run() -> dict[str, Any] | None:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

    return await asyncio.to_thread(_run)


async def fetch_all(
    conn: pymysql.Connection, sql: str, params: tuple[Any, ...] | None = None
) -> list[dict[str, Any]]:
    def _run() -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    return await asyncio.to_thread(_run)


async def execute(
    conn: pymysql.Connection, sql: str, params: tuple[Any, ...] | None = None
) -> int:
    def _run() -> int:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount

    return await asyncio.to_thread(_run)


async def execute_returning_id(
    conn: pymysql.Connection, sql: str, params: tuple[Any, ...] | None = None
) -> int:
    def _run() -> int:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid

    return await asyncio.to_thread(_run)
