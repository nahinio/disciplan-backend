from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user
from app.db.session import get_connection
from app.repositories import chat_repo
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.get("/groups")
async def list_groups(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        groups = await chat_repo.list_user_groups(conn, user["id"])
    return {"items": groups}


@router.get("/groups/{group_id}/messages")
async def poll_messages(
    group_id: int,
    user: dict = Depends(get_current_user),
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
) -> dict:
    """Polled every ~3 seconds while chat tab is open."""
    return await chat_service.poll_messages(group_id, user["id"], after_id=after_id, limit=limit)


@router.post("/groups/{group_id}/messages")
async def send_message(
    group_id: int,
    body: SendMessageRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await chat_service.send_message(group_id, user["id"], body.body)
    except PermissionError as exc:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
