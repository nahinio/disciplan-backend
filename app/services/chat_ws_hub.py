"""In-memory WebSocket fan-out per chat group."""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket


class ChatWsHub:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = {}
        self._meta: dict[WebSocket, dict[str, int]] = {}

    async def connect(self, websocket: WebSocket, *, group_id: int, user_id: int) -> None:
        await websocket.accept()
        self._rooms.setdefault(group_id, set()).add(websocket)
        self._meta[websocket] = {"group_id": group_id, "user_id": user_id}

    def disconnect(self, websocket: WebSocket) -> None:
        meta = self._meta.pop(websocket, None)
        if not meta:
            return
        group_id = meta["group_id"]
        room = self._rooms.get(group_id)
        if room:
            room.discard(websocket)
            if not room:
                self._rooms.pop(group_id, None)

    async def broadcast(self, group_id: int, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._rooms.get(group_id, set())):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


chat_ws_hub = ChatWsHub()
