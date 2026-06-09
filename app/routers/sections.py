from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_roles
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, chat_repo, enrollment_repo, practice_repo, section_repo
from app.schemas.academic import (
    AnswerDoubtRequest,
    CreateAnnouncementRequest,
    CreateDoubtRequest,
    UpdateAnnouncementRequest,
    VoteRequest,
)
from app.schemas.phase3 import (
    CreateAnnouncementCommentRequest,
    CreatePracticeProblemRequest,
    CreateSectionResourceRequest,
    PinAnnouncementCommentRequest,
    UpdateSectionPracticeProblemRequest,
    UpdateSectionResourceRequest,
)
from app.schemas.enrollment import CreateEnrollmentRequestBody
from app.schemas.onboarding import RoutineSection
from app.services import gamification_service

router = APIRouter(prefix="/sections", tags=["sections"])


async def _resolve_section(conn, course_code: str, section_label: str) -> dict:
    section = await academic_repo.find_section(conn, course_code, section_label)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


async def _require_access(conn, section_id: int, user: dict) -> None:
    if not await section_repo._user_can_access_section(
        conn, section_id, user["id"], user["role_code"]
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No section access")


@router.post("/enrollments")
async def enroll_section(
    body: RoutineSection,
    user: dict = Depends(require_roles("student", "faculty")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, body.course_code, body.section_label)
        if user["role_code"] == "faculty":
            await academic_repo.assign_faculty(conn, section["id"], user["id"])
            await chat_repo.ensure_section_chat_member(
                conn,
                section_id=section["id"],
                user_id=user["id"],
                group_name=f"{body.course_code} {body.section_label} Chat",
                created_by_user_id=user["id"],
            )
        else:
            await academic_repo.enroll_student(conn, section["id"], user["id"])
            await chat_repo.ensure_section_chat_member(
                conn,
                section_id=section["id"],
                user_id=user["id"],
                group_name=f"{body.course_code} {body.section_label} Chat",
                created_by_user_id=user["id"],
            )
    return {"section_id": section["id"], "message": "Enrolled"}


@router.get("/enrollment-requests")
async def list_my_enrollment_requests(
    user: dict = Depends(require_roles("student")),
) -> dict:
    async with get_connection() as conn:
        items = await enrollment_repo.list_requests_for_student(conn, user["id"])
    return {"items": items}


@router.post("/enrollment-requests", status_code=status.HTTP_201_CREATED)
async def create_enrollment_request(
    body: CreateEnrollmentRequestBody,
    user: dict = Depends(require_roles("student")),
) -> dict:
    try:
        async with transaction() as conn:
            request_id = await enrollment_repo.create_request(
                conn,
                student_user_id=user["id"],
                course_code=body.course_code.strip().upper(),
                section_label=body.section_label.strip().upper(),
                message=body.message,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"id": request_id, "message": "Enrollment request submitted"}


@router.delete("/enrollment-requests/{request_id}")
async def cancel_enrollment_request(
    request_id: int,
    user: dict = Depends(require_roles("student")),
) -> dict:
    async with transaction() as conn:
        ok = await enrollment_repo.cancel_request(
            conn, request_id=request_id, student_user_id=user["id"]
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found or cannot be cancelled",
        )
    return {"message": "Request cancelled"}


@router.delete("/enrollments/{course_code}/{section_label}")
async def drop_section(
    course_code: str,
    section_label: str,
    user: dict = Depends(require_roles("student")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        ok = await academic_repo.drop_student(conn, section["id"], user["id"])
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not enrolled")
    return {"message": "Dropped"}


@router.get("/{course_code}/{section_label}/announcements")
async def list_announcements(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        await _require_access(conn, section["id"], user)
        items = await section_repo.list_announcements(conn, section["id"])
    return {"section_id": section["id"], "items": items}


@router.post("/{course_code}/{section_label}/announcements")
async def create_announcement(
    course_code: str,
    section_label: str,
    body: CreateAnnouncementRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        ann_id = await section_repo.create_announcement(
            conn,
            section_id=section["id"],
            author_user_id=user["id"],
            title=body.title,
            body=body.body,
            is_pinned=body.is_pinned,
        )
    return {"id": ann_id, "message": "Announcement created"}


@router.patch("/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: int,
    body: UpdateAnnouncementRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await section_repo.update_announcement(
            conn,
            announcement_id=announcement_id,
            title=body.title,
            body=body.body,
            is_pinned=body.is_pinned,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return {"message": "Announcement updated"}


@router.delete("/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await section_repo.delete_announcement(conn, announcement_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    return {"message": "Announcement deleted"}


@router.get("/{course_code}/{section_label}/doubts")
async def list_doubts(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        await _require_access(conn, section["id"], user)
        items = await section_repo.list_doubts(conn, section["id"])
    return {"section_id": section["id"], "items": items}


@router.get("/doubts/search")
async def search_doubts(
    user: dict = Depends(get_current_user),
    q: str = Query(default="", max_length=200),
    course_code: str | None = Query(default=None),
    section_label: str | None = Query(default=None),
    status: str = Query(default="all", pattern="^(all|resolved)$"),
    limit: int = Query(default=40, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Fuzzy search across doubts in courses the user is enrolled in or teaches."""
    async with get_connection() as conn:
        items, total = await section_repo.search_doubts(
            conn,
            user["id"],
            user["role_code"],
            q=q,
            course_code=course_code,
            section_label=section_label,
            status=status,  # type: ignore[arg-type]
            limit=limit,
            offset=offset,
        )
    return {"items": items, "total": total, "q": q.strip(), "status": status}


@router.get("/doubts/{doubt_id}")
async def get_doubt(doubt_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        doubt = await section_repo.get_doubt(conn, doubt_id)
        if not doubt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doubt not found")
        await _require_access(conn, doubt["section_id"], user)
        answers = await section_repo.list_answers(conn, doubt_id)
    return {**doubt, "answers": answers}


@router.post("/{course_code}/{section_label}/doubts")
async def create_doubt(
    course_code: str,
    section_label: str,
    body: CreateDoubtRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        await _require_access(conn, section["id"], user)
        doubt_id = await section_repo.create_doubt(
            conn,
            section_id=section["id"],
            author_user_id=user["id"],
            title=body.title,
            body=body.body,
        )
    return {"id": doubt_id, "message": "Doubt posted"}


@router.post("/doubts/{doubt_id}/answers")
async def answer_doubt(
    doubt_id: int,
    body: AnswerDoubtRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        doubt = await section_repo.get_doubt(conn, doubt_id)
        if not doubt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doubt not found")
        is_faculty = user["role_code"] in ("faculty", "admin")
        answer_id = await section_repo.answer_doubt(
            conn,
            doubt_id=doubt_id,
            author_user_id=user["id"],
            body=body.body,
            is_faculty=is_faculty,
            parent_answer_id=body.parent_answer_id,
        )
        if is_faculty:
            await section_repo.verify_doubt(
                conn, doubt_id=doubt_id, verifier_user_id=user["id"]
            )
        elif user["role_code"] == "student":
            await gamification_service.on_answer_posted(conn, user["id"], doubt_id)
    return {"id": answer_id, "message": "Answer posted"}


@router.post("/doubts/{doubt_id}/verify")
async def verify_doubt(
    doubt_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await section_repo.verify_doubt(
            conn, doubt_id=doubt_id, verifier_user_id=user["id"]
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doubt not found")
    return {"message": "Doubt marked as solved"}


@router.post("/doubts/answers/{answer_id}/accept")
async def accept_doubt_answer(
    answer_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        try:
            result = await section_repo.accept_doubt_answer(
                conn, answer_id=answer_id, verifier_user_id=user["id"]
            )
        except section_repo.DoubtAcceptError as exc:
            code = str(exc)
            if code == "not_found":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found"
                ) from exc
            if code == "faculty_author":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only student answers can be accepted as official solutions",
                ) from exc
            if code == "already_accepted":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This doubt already has an official solution",
                ) from exc
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code) from exc

        await _require_access(conn, result["section_id"], user)
        new_achievements = await gamification_service.on_faculty_endorsed_answer(
            conn,
            author_user_id=result["author_user_id"],
            answer_id=answer_id,
            doubt_id=result["doubt_id"],
        )
    return {
        "message": "Answer accepted as official solution",
        "new_achievements": new_achievements,
    }


@router.post("/doubts/answers/{answer_id}/verify")
async def verify_doubt_answer(
    answer_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    """Legacy alias — accepts student answer as official solution."""
    return await accept_doubt_answer(answer_id, user)


@router.post("/doubts/{doubt_id}/vote")
async def vote_doubt(
    doubt_id: int,
    body: VoteRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        doubt = await section_repo.get_doubt(conn, doubt_id)
        if not doubt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doubt not found")
        await _require_access(conn, doubt["section_id"], user)
        await section_repo.vote_doubt(conn, doubt_id, user["id"], body.direction)
    return {"message": "Vote recorded"}


@router.get("/{course_code}/{section_label}/resources")
async def list_resources(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        await _require_access(conn, section["id"], user)
        items = await section_repo.list_resources(conn, section["id"])
    return {"section_id": section["id"], "items": items}


@router.post("/{course_code}/{section_label}/resources")
async def create_resource(
    course_code: str,
    section_label: str,
    body: CreateSectionResourceRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        rid = await section_repo.create_resource(
            conn,
            section_id=section["id"],
            title=body.title,
            description=body.description,
            resource_kind=body.resource_kind,
            file_id=body.file_id,
            external_url=body.external_url,
            mime_category=body.mime_category,
            created_by_user_id=user["id"],
        )
    return {"id": rid, "message": "Resource created"}


@router.patch("/resources/{resource_id}")
async def update_resource(
    resource_id: int,
    body: UpdateSectionResourceRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        resource = await section_repo.get_resource(conn, resource_id)
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        await _require_access(conn, int(resource["section_id"]), user)
        ok = await section_repo.update_resource(
            conn,
            resource_id,
            title=body.title,
            description=body.description,
            external_url=body.external_url,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")
    return {"message": "Resource updated"}


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        resource = await section_repo.get_resource(conn, resource_id)
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        await _require_access(conn, int(resource["section_id"]), user)
        ok = await section_repo.delete_resource(conn, resource_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return {"message": "Resource deleted"}


@router.get("/announcements/{announcement_id}/comments")
async def list_announcement_comments(
    announcement_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        items = await section_repo.list_announcement_comments(conn, announcement_id)
    return {"announcement_id": announcement_id, "items": items}


@router.post("/announcements/{announcement_id}/comments")
async def create_announcement_comment(
    announcement_id: int,
    body: CreateAnnouncementCommentRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        cid = await section_repo.create_announcement_comment(
            conn,
            announcement_id=announcement_id,
            author_user_id=user["id"],
            body=body.body,
            parent_comment_id=body.parent_comment_id,
        )
    return {"id": cid, "message": "Comment posted"}


@router.patch("/announcements/comments/{comment_id}/pin")
async def pin_announcement_comment(
    comment_id: int,
    body: PinAnnouncementCommentRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await section_repo.pin_announcement_comment(
            conn, comment_id, pinned=body.pinned, pinner_user_id=user["id"]
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return {"message": "Pin updated"}


@router.delete("/announcements/comments/{comment_id}")
async def delete_announcement_comment(
    comment_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        ok = await section_repo.delete_announcement_comment(
            conn, comment_id, user["id"], user["role_code"]
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return {"message": "Comment deleted"}


@router.get("/{course_code}/{section_label}/practice/problems")
async def list_section_practice(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        await _require_access(conn, section["id"], user)
        central = await practice_repo.list_problems(
            conn, section["course_id"], central_only=True
        )
        local = await practice_repo.list_problems(
            conn, section["course_id"], section_id=section["id"]
        )
        for row in central:
            row["scope"] = "course"
        for row in local:
            row["scope"] = "section"
        items = central + local
    return {"section_id": section["id"], "items": items}


@router.post("/{course_code}/{section_label}/practice/problems")
async def create_section_practice(
    course_code: str,
    section_label: str,
    body: CreatePracticeProblemRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        result = await practice_repo.create_problem(
            conn,
            course_id=section["course_id"],
            topic_id=body.topic_id,
            creator_user_id=user["id"],
            question=body.question,
            answer=body.answer,
            assessment_type_code=body.assessment_type_code,
            difficulty_score=body.difficulty_score,
            question_image_file_id=body.question_image_file_id,
            answer_image_file_id=body.answer_image_file_id,
            section_id=section["id"],
            tags=body.tags,
        )
    return {**result, "message": "Problem created"}


@router.patch("/practice/problems/{problem_id}")
async def update_section_practice(
    problem_id: int,
    body: UpdateSectionPracticeProblemRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        problem = await practice_repo.get_problem(conn, problem_id)
        if not problem or problem.get("section_id") is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section practice problem not found",
            )
        section_id = int(problem["section_id"])
        await _require_access(conn, section_id, user)
        updates = body.model_dump(exclude_unset=True)
        if "topic_id" in updates and body.topic_id is not None:
            topic = await practice_repo.get_topic_for_course(
                conn, body.topic_id, int(problem["course_id"])
            )
            if not topic:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid topic")
        ok = await practice_repo.update_section_problem(
            conn,
            problem_id,
            section_id,
            question=body.question,
            answer=body.answer,
            topic_id=body.topic_id,
            topic_id_set="topic_id" in updates,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")
    return {"message": "Problem updated"}


@router.delete("/practice/problems/{problem_id}")
async def delete_section_practice(
    problem_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        problem = await practice_repo.get_problem(conn, problem_id)
        if not problem or problem.get("section_id") is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section practice problem not found",
            )
        section_id = int(problem["section_id"])
        await _require_access(conn, section_id, user)
        ok = await practice_repo.delete_section_problem(conn, problem_id, section_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")
    return {"message": "Problem deleted"}
