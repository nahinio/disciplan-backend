from fastapi import APIRouter

from app.config import get_settings
from app.db.session import fetch_one, get_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    db_ok = False
    try:
        async with get_connection() as conn:
            row = await fetch_one(conn, "SELECT 1 AS ok")
            db_ok = row is not None and row.get("ok") == 1
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "database": "connected" if db_ok else "disconnected",
    }
