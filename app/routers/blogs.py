from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_roles
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, blog_repo, practice_repo
from app.schemas.academic import (
    CreateBlogPostRequest,
    CreateCommentRequest,
    UpdateBlogPostRequest,
    VoteRequest,
)
from app.services import gamification_service

router = APIRouter(prefix="/blogs", tags=["blogs"])


@router.get("")
async def list_all_posts(
    _: dict = Depends(get_current_user),
    course_code: str | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    limit: int = Query(default=30, le=50),
) -> dict:
    async with get_connection() as conn:
        course_id = None
        if course_code:
            course = await academic_repo.get_course_by_code(conn, course_code)
            if not course:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
            course_id = course["id"]
            if topic_id is not None:
                topic = await practice_repo.get_topic_for_course(conn, topic_id, course_id)
                if not topic:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found for course")
        items = await blog_repo.list_posts(
            conn, course_id=course_id, topic_id=topic_id, limit=limit
        )
    return {"items": items}


@router.get("/posts/{post_id}")
async def get_post(post_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        post = await blog_repo.get_post(conn, post_id, viewer_user_id=user["id"])
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        comments = await blog_repo.list_comments(conn, post_id)
    return {**post, "comments": comments}


@router.post("")
async def create_post(
    body: CreateBlogPostRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, body.course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        if body.topic_id is not None:
            topic = await practice_repo.get_topic_for_course(
                conn, body.topic_id, course["id"]
            )
            if not topic:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Topic not found for course",
                )

        author_role = user["role_code"] if user["role_code"] in ("faculty", "admin") else "student"
        auto_verified = author_role in ("faculty", "admin")

        post_id = await blog_repo.create_post(
            conn,
            course_id=course["id"],
            topic_id=body.topic_id,
            author_user_id=user["id"],
            author_role_code=author_role,
            title=body.title,
            excerpt=body.excerpt,
            body_html=body.body_html,
            read_time_min=body.read_time_min,
            is_verified=auto_verified,
            verified_by_user_id=user["id"] if auto_verified else None,
            cover_image_file_id=body.cover_image_file_id,
        )
        if body.tags:
            await blog_repo.set_post_tags(
                conn,
                post_id=post_id,
                course_id=course["id"],
                tag_names=body.tags,
            )
        await gamification_service.on_blog_publish(conn, user["id"], post_id)
    return {"id": post_id, "message": "Post published", "is_verified": auto_verified}


@router.post("/posts/{post_id}/verify")
async def verify_post(
    post_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await blog_repo.verify_post(conn, post_id, verifier_user_id=user["id"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post not found or only student posts can be verified",
        )
    return {"message": "Post verified"}


@router.patch("/posts/{post_id}")
async def update_post(
    post_id: int,
    body: UpdateBlogPostRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    async with transaction() as conn:
        ok = await blog_repo.update_post(
            conn,
            post_id,
            author_user_id=user["id"],
            title=updates.get("title"),
            excerpt=updates.get("excerpt"),
            body_html=updates.get("body_html"),
            read_time_min=updates.get("read_time_min"),
            cover_image_file_id=updates["cover_image_file_id"]
            if "cover_image_file_id" in updates
            else ...,
            is_admin=user["role_code"] == "admin",
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found or forbidden")
    return {"message": "Post updated"}


@router.delete("/posts/{post_id}")
async def delete_post(post_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with transaction() as conn:
        ok = await blog_repo.delete_post(
            conn,
            post_id,
            author_user_id=user["id"],
            is_admin=user["role_code"] == "admin",
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found or forbidden")
    return {"message": "Post deleted"}


@router.post("/posts/{post_id}/pin")
async def pin_post(
    post_id: int,
    pinned: bool = True,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        ok = await blog_repo.set_pinned(conn, post_id, pinned)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return {"message": "Pin updated"}


@router.post("/posts/{post_id}/comments")
async def add_comment(
    post_id: int,
    body: CreateCommentRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        comment_id = await blog_repo.add_comment(
            conn,
            post_id=post_id,
            author_user_id=user["id"],
            body=body.body,
            parent_comment_id=body.parent_comment_id,
        )
    return {"id": comment_id, "message": "Comment added"}


@router.post("/posts/{post_id}/vote")
async def vote_post(
    post_id: int,
    body: VoteRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        author_id, counts = await blog_repo.vote_post(
            conn, post_id, user["id"], body.direction
        )
        if author_id:
            await gamification_service.on_vote(
                conn,
                author_user_id=author_id,
                voter_user_id=user["id"],
                direction=body.direction,
                reference_type="blog_post",
                reference_id=post_id,
            )
    return {"message": "Vote recorded", **counts}
