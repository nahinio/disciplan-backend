from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.db.session import get_connection
from app.repositories import notification_repo
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/unread-count")
async def unread_count(user: dict = Depends(get_current_user)) -> dict:
    """Polled by frontend bell icon every ~8 seconds."""
    async with get_connection() as conn:
        count = await notification_repo.get_unread_count(conn, user["id"])
    return {"unread_count": count, "poll_interval_sec": 8}


@router.get("")
async def list_notifications(
    user: dict = Depends(get_current_user),
    only_unread: bool = Query(default=False),
    after_id: int | None = Query(default=None),
    limit: int = Query(default=20, le=50),
) -> dict:
    async with get_connection() as conn:
        items = await notification_repo.list_notifications(
            conn, user["id"], only_unread=only_unread, after_id=after_id, limit=limit
        )
    return {
        "items": items,
        "has_more": len(items) == limit,
        "next_cursor": str(items[-1]["id"]) if items else None,
    }


@router.patch("/{notification_id}/read", response_model=MessageResponse)
async def mark_notification_read(
    notification_id: int,
    user: dict = Depends(get_current_user),
) -> MessageResponse:
    async with get_connection() as conn:
        ok = await notification_repo.mark_read(conn, user["id"], notification_id)
    if not ok:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return MessageResponse(message="Marked as read")


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_read(user: dict = Depends(get_current_user)) -> MessageResponse:
    async with get_connection() as conn:
        await notification_repo.mark_all_read(conn, user["id"])
    return MessageResponse(message="All notifications marked as read")
