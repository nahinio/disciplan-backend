from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.db.session import get_connection
from app.repositories import admin_repo

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/global")
async def list_global_announcements(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        items = await admin_repo.list_active_global_announcements(conn, user["role_code"])
    return {"items": items}
