from __future__ import annotations

import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.db.session import fetch_one, get_connection
from app.repositories import chat_repo
from app.services import chat_service
from app.services.chat_ws_hub import chat_ws_hub
from app.utils.security import decode_access_token

router = APIRouter(tags=["chat-ws"])


async def _authenticate_ws(token: str) -> dict | None:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        return None

    async with get_connection() as conn:
        user = await fetch_one(
            conn,
            """
            SELECT u.id, r.code AS role_code, us.code AS status_code
            FROM users u
            INNER JOIN roles r ON r.id = u.role_id
            INNER JOIN user_statuses us ON us.id = u.status_id
            WHERE u.id = %s
            """,
            (user_id,),
        )
    if not user or user["status_code"] == "suspended":
        return None
    return {"id": user_id, "role_code": user["role_code"]}


@router.websocket("/chat/ws/{group_id}")
async def chat_websocket(
    websocket: WebSocket,
    group_id: int,
    token: str = Query(...),
) -> None:
    user = await _authenticate_ws(token)
    if not user:
        await websocket.close(code=4401)
        return

    async with get_connection() as conn:
        member = await fetch_one(
            conn,
            """
            SELECT 1 FROM chat_group_members
            WHERE group_id = %s AND user_id = %s AND left_at IS NULL
            """,
            (group_id, user["id"]),
        )
    if not member:
        await websocket.close(code=4403)
        return

    await chat_ws_hub.connect(websocket, group_id=group_id, user_id=user["id"])
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "message":
                continue
            body = str(data.get("body", "")).strip()
            if not body:
                continue
            try:
                await chat_service.send_message(group_id, user["id"], body[:4000])
            except PermissionError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Forbidden"}))
    except WebSocketDisconnect:
        pass
    finally:
        chat_ws_hub.disconnect(websocket)
