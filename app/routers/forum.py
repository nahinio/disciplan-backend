from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, forum_repo
from app.services import gamification_service
from app.schemas.academic import VoteRequest
from app.schemas.phase3 import (
    CreateForumReplyRequest,
    CreateForumThreadRequest,
    UpdateForumReplyRequest,
    UpdateForumThreadRequest,
)

router = APIRouter(prefix="/forum", tags=["forum"])


@router.get("/feed")
async def list_feed(
    user: dict = Depends(get_current_user),
    course_code: str | None = Query(default=None),
    thread_type: str | None = Query(
        default=None, pattern="^(advice|resource|discussion)$"
    ),
    sort: str = Query(default="recent", pattern="^(recent|top)$"),
    mine_only: bool = Query(default=False),
    limit: int = Query(default=50, le=100),
) -> dict:
    async with get_connection() as conn:
        course_ids = await academic_repo.list_accessible_course_ids(
            conn, user["id"], user["role_code"]
        )
        if course_code:
            course = await academic_repo.get_course_by_code(conn, course_code)
            if not course:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
                )
            if not await academic_repo.user_has_course_access(
                conn, user["id"], user["role_code"], course["id"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
                )
            course_ids = [course["id"]]

        items = await forum_repo.list_feed(
            conn,
            course_ids,
            thread_type_code=thread_type,
            author_user_id=user["id"] if mine_only else None,
            exclude_doubt=True,
            sort=sort,
            limit=limit,
            viewer_user_id=user["id"],
        )
    return {"items": items, "course_code": course_code, "sort": sort, "mine_only": mine_only}


@router.get("/courses/{course_code}/threads")
async def list_threads(
    course_code: str,
    user: dict = Depends(get_current_user),
    thread_type: str | None = Query(
        default=None, pattern="^(doubt|advice|resource|discussion)$"
    ),
    mine_only: bool = Query(default=False),
    limit: int = Query(default=50, le=100),
) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], course["id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        items = await forum_repo.list_threads(
            conn,
            course["id"],
            thread_type_code=thread_type,
            author_user_id=user["id"] if mine_only else None,
            limit=limit,
            viewer_user_id=user["id"],
        )
    return {"course_code": course_code, "items": items, "mine_only": mine_only}


@router.get("/courses/{course_code}/stats")
async def forum_stats(course_code: str, user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], course["id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        stats = await forum_repo.forum_stats(conn, course["id"])
    return {"course_code": course_code, **stats}


@router.post("/courses/{course_code}/threads")
async def create_thread(
    course_code: str,
    body: CreateForumThreadRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], course["id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        try:
            thread_id = await forum_repo.create_thread(
                conn,
                course_id=course["id"],
                author_user_id=user["id"],
                thread_type_code=body.thread_type_code,
                title=body.title,
                body=body.body,
                image_file_ids=body.image_file_ids,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    return {"id": thread_id, "message": "Thread created"}


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        thread = await forum_repo.get_thread(conn, thread_id, viewer_user_id=user["id"])
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], thread["course_id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        replies = await forum_repo.list_replies(conn, thread_id)
    return {**thread, "replies": replies}


@router.post("/threads/{thread_id}/replies")
async def add_reply(
    thread_id: int,
    body: CreateForumReplyRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        thread = await forum_repo.get_thread(conn, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], thread["course_id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        if thread["is_locked"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Thread is locked")
        reply_id = await forum_repo.add_reply(
            conn,
            thread_id=thread_id,
            author_user_id=user["id"],
            body=body.body,
            parent_reply_id=body.parent_reply_id,
        )
    return {"id": reply_id, "message": "Reply added"}


@router.post("/threads/{thread_id}/vote")
async def vote_thread(
    thread_id: int,
    body: VoteRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        thread = await forum_repo.get_thread(conn, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], thread["course_id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        author_id = await forum_repo.vote_thread(conn, thread_id, user["id"], body.direction)
        if author_id:
            await gamification_service.on_vote(
                conn,
                author_user_id=author_id,
                voter_user_id=user["id"],
                direction=body.direction,
                reference_type="forum_thread",
                reference_id=thread_id,
            )
    return {"message": "Vote recorded"}


@router.post("/replies/{reply_id}/vote")
async def vote_reply(
    reply_id: int,
    body: VoteRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        author_id = await forum_repo.vote_reply(conn, reply_id, user["id"], body.direction)
        if author_id:
            await gamification_service.on_vote(
                conn,
                author_user_id=author_id,
                voter_user_id=user["id"],
                direction=body.direction,
                reference_type="forum_thread",
                reference_id=reply_id,
            )
    return {"message": "Vote recorded"}


@router.patch("/threads/{thread_id}")
async def update_own_thread(
    thread_id: int,
    body: UpdateForumThreadRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        thread = await forum_repo.get_thread(conn, thread_id)
        if not thread:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
        if not await academic_repo.user_has_course_access(
            conn, user["id"], user["role_code"], thread["course_id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No course access"
            )
        ok = await forum_repo.update_thread_as_author(
            conn,
            thread_id,
            user["id"],
            title=body.title,
            body=body.body,
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or you are not the author",
        )
    return {"message": "Thread updated"}


@router.delete("/threads/{thread_id}")
async def delete_own_thread(
    thread_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        ok = await forum_repo.delete_thread_as_author(conn, thread_id, user["id"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found or you are not the author",
        )
    return {"message": "Thread deleted"}


@router.patch("/replies/{reply_id}")
async def update_own_reply(
    reply_id: int,
    body: UpdateForumReplyRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        ok = await forum_repo.update_reply_as_author(
            conn, reply_id, user["id"], body=body.body
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found or you are not the author",
        )
    return {"message": "Reply updated"}


@router.delete("/replies/{reply_id}")
async def delete_own_reply(
    reply_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        ok = await forum_repo.delete_reply_as_author(conn, reply_id, user["id"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reply not found or you are not the author",
        )
    return {"message": "Reply deleted"}
