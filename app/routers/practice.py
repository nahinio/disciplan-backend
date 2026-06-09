from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_roles
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, practice_repo
from app.schemas.phase3 import (
    CreatePastPaperRequest,
    CreatePracticeProblemRequest,
    CreatePracticeTopicRequest,
)

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/courses/{course_code}/topics")
async def list_topics(course_code: str, _: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        items = await practice_repo.list_topics_with_counts(conn, course["id"])
    return {"course_code": course_code, "items": items}


@router.post("/courses/{course_code}/topics")
async def create_topic(
    course_code: str,
    body: CreatePracticeTopicRequest,
    _: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        topic_id = await practice_repo.create_topic(
            conn,
            course_id=course["id"],
            title=body.title,
            week_number=body.week_number,
            sort_order=body.sort_order,
        )
    return {"id": topic_id, "message": "Topic created"}


@router.get("/courses/{course_code}/problems")
async def list_problems(
    course_code: str,
    _: dict = Depends(get_current_user),
    topic_id: int | None = Query(default=None),
    term: str | None = Query(default=None),
) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        items = await practice_repo.list_problems(
            conn,
            course["id"],
            topic_id=topic_id,
            assessment_type_code=term,
            central_only=True,
        )
    return {"course_code": course_code, "items": items}


@router.post("/courses/{course_code}/problems")
async def create_problem(
    course_code: str,
    body: CreatePracticeProblemRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if body.topic_id is not None:
            topic = await practice_repo.get_topic_for_course(
                conn, body.topic_id, course["id"]
            )
            if not topic:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found"
                )

        result = await practice_repo.create_problem(
            conn,
            course_id=course["id"],
            topic_id=body.topic_id,
            creator_user_id=user["id"],
            question=body.question,
            answer=body.answer,
            assessment_type_code=body.assessment_type_code,
            difficulty_score=body.difficulty_score,
            question_image_file_id=body.question_image_file_id,
            answer_image_file_id=body.answer_image_file_id,
            tags=body.tags,
        )
    return {
        "id": result["id"],
        "problem_number": result["problem_number"],
        "message": "Problem created",
    }


@router.get("/courses/{course_code}/past-papers")
async def list_past_papers(course_code: str, _: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        items = await practice_repo.list_past_papers(conn, course["id"])
    return {"course_code": course_code, "items": items}


@router.post("/courses/{course_code}/past-papers")
async def create_past_paper(
    course_code: str,
    body: CreatePastPaperRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        paper_id = await practice_repo.create_past_paper(
            conn,
            course_id=course["id"],
            title=body.title,
            exam_year=body.exam_year,
            file_id=body.file_id,
            uploaded_by_user_id=user["id"],
        )
    return {"id": paper_id, "message": "Past paper added"}
