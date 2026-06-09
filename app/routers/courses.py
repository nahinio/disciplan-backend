from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.db.session import fetch_all, get_connection
from app.repositories import academic_repo

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/meta/departments")
async def list_departments() -> dict:
    async with get_connection() as conn:
        items = await fetch_all(conn, "SELECT id, code, name FROM departments ORDER BY code")
    return {"items": items}


@router.get("")
async def list_courses(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        if user["role_code"] == "admin":
            catalogue = await academic_repo.list_catalogue(conn)
            return {"items": catalogue, "view": "catalogue"}

        my_sections = await academic_repo.list_user_sections(
            conn, user["id"], user["role_code"]
        )
        if my_sections:
            return {"items": my_sections, "view": "mine"}

        offerings = await academic_repo.list_offerings(conn)
        return {"items": offerings, "view": "offerings"}


@router.get("/catalogue")
async def catalogue(_: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        items = await academic_repo.list_catalogue(conn)
    return {"items": items}


@router.get("/offerings")
async def offerings() -> dict:
    """Full routine listing for onboarding course picker."""
    async with get_connection() as conn:
        items = await academic_repo.list_offerings(conn)
    return {"items": items}


@router.get("/{course_code}")
async def get_course(course_code: str, _: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        sections = await academic_repo.get_sections_for_course(conn, course["id"])
        syllabus = await academic_repo.get_syllabus_topics(conn, course["id"])
    return {**course, "sections": sections, "syllabus_topics": syllabus}
