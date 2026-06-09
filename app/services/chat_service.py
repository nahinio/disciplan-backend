from __future__ import annotations

from app.db.session import transaction
from app.repositories import chat_repo, notification_repo
from app.db.session import fetch_one
from app.services.chat_ws_hub import chat_ws_hub


async def poll_messages(group_id: int, user_id: int, after_id: int = 0, limit: int = 50) -> dict:
    async with transaction() as conn:
        messages = await chat_repo.get_messages_since(
            conn, group_id, user_id, after_id=after_id, limit=limit
        )
        if messages:
            last_id = messages[-1]["id"]
            await chat_repo.mark_messages_read(conn, group_id, user_id, last_id)

    return {
        "items": messages,
        "has_more": len(messages) == limit,
        "next_cursor": str(messages[-1]["id"]) if messages else None,
    }


def _course_slug(course_code: str) -> str:
    return course_code.lower().replace(" ", "-")


async def send_message(group_id: int, sender_user_id: int, body: str) -> dict:
    preview = body[:100]
    action_path = "/dashboard"

    async with transaction() as conn:
        group_row = await fetch_one(
            conn,
            """
            SELECT c.code AS course_code, s.section_label
            FROM chat_groups cg
            INNER JOIN sections s ON s.id = cg.section_id
            INNER JOIN courses c ON c.id = s.course_id
            WHERE cg.id = %s
            """,
            (group_id,),
        )
        if group_row:
            slug = _course_slug(group_row["course_code"])
            section = group_row["section_label"]
            action_path = f"/courses/{slug}/section?section={section}&tab=chat"

        message_id = await chat_repo.send_message(
            conn, group_id=group_id, sender_user_id=sender_user_id, body=body
        )
        row = await chat_repo.get_message_by_id(conn, message_id, sender_user_id)
        await notification_repo.create_notifications_for_group_message(
            conn,
            group_id=group_id,
            message_id=message_id,
            sender_user_id=sender_user_id,
            body_preview=preview,
            action_path=action_path,
        )

    payload = {"type": "chat_message", "item": row} if row else {"type": "chat_message", "id": message_id}
    await chat_ws_hub.broadcast(group_id, payload)

    return {"id": message_id, "body": body, "item": row}
