"""Sync MySQL pool (PyMySQL + Aiven SSL) — reliable on Windows."""

from __future__ import annotations

import ssl
from pathlib import Path
from queue import Empty, Queue
from threading import Lock

import pymysql
import pymysql.cursors

from app.config import get_settings

_pool: Queue[pymysql.Connection] | None = None
_pool_size: int = 0
_lock = Lock()


def _build_ssl() -> ssl.SSLContext | None:
    settings = get_settings()
    if not settings.db_ssl:
        return None

    ctx = ssl.create_default_context()
    ca_pem = settings.db_ssl_ca.strip() if settings.db_ssl_ca else ""
    if ca_pem:
        ctx.load_verify_locations(cadata=ca_pem)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    elif settings.db_ssl_ca_path:
        ca_path = Path(settings.db_ssl_ca_path)
        if ca_path.exists():
            ctx.load_verify_locations(cafile=str(ca_path))
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _create_connection() -> pymysql.Connection:
    settings = get_settings()
    connect_kwargs: dict = {
        "host": settings.db_host,
        "port": settings.db_port,
        "user": settings.db_user,
        "password": settings.db_password,
        "database": settings.db_name,
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 15,
    }
    ssl_ctx = _build_ssl()
    if ssl_ctx is not None:
        connect_kwargs["ssl"] = ssl_ctx
    return pymysql.connect(**connect_kwargs)


def init_pool() -> None:
    """Create sync connection pool (call once on startup)."""
    global _pool, _pool_size
    settings = get_settings()
    with _lock:
        if _pool is not None:
            return
        _pool = Queue(maxsize=settings.db_pool_max)
        _pool_size = settings.db_pool_min
        for _ in range(settings.db_pool_min):
            _pool.put(_create_connection())


def close_pool() -> None:
    global _pool, _pool_size
    with _lock:
        if _pool is None:
            return
        while True:
            try:
                conn = _pool.get_nowait()
                conn.close()
            except Empty:
                break
        _pool = None
        _pool_size = 0


def _healthy_connection(conn: pymysql.Connection) -> pymysql.Connection:
    try:
        conn.ping(reconnect=True)
        return conn
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return _create_connection()


def acquire() -> pymysql.Connection:
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() on startup.")
    try:
        conn = _pool.get(timeout=10)
    except Empty:
        with _lock:
            if _pool.qsize() < get_settings().db_pool_max:
                return _create_connection()
        conn = _pool.get(timeout=30)
    return _healthy_connection(conn)


def release(conn: pymysql.Connection) -> None:
    if _pool is None:
        conn.close()
        return
    try:
        conn.ping(reconnect=True)
        _pool.put_nowait(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        try:
            _pool.put_nowait(_create_connection())
        except Exception:
            pass
