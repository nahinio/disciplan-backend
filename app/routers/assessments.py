from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user, require_roles
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, assessment_repo, grade_repo
from app.services import grading_integration_service
from app.schemas.phase3 import (
    CreateGradeComponentRequest,
    CreatePortalRequest,
    GradeSubmissionRequest,
    SubmitAssessmentRequest,
    UpdateGradeComponentRequest,
    UpdatePortalRequest,
    UpsertGradeRequest,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _resolve_section(conn, course_code: str, section_label: str) -> dict:
    section = await academic_repo.find_section(conn, course_code, section_label)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


@router.get("/sections/{course_code}/{section_label}/portals")
async def list_portals(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        if not await assessment_repo.ensure_section_access(
            conn, section["id"], user["id"], user["role_code"]
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
        items = await assessment_repo.list_portals(conn, section["id"])
    return {"section_id": section["id"], "items": items}


@router.post("/sections/{course_code}/{section_label}/portals")
async def create_portal(
    course_code: str,
    section_label: str,
    body: CreatePortalRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        portal_id = await assessment_repo.create_portal(
            conn,
            section_id=section["id"],
            creator_user_id=user["id"],
            title=body.title,
            description=body.description,
            assessment_type_code=body.assessment_type_code,
            opens_at=_parse_dt(body.opens_at),
            closes_at=_parse_dt(body.closes_at),
            max_score=body.max_score,
        )
        await grading_integration_service.on_portal_created(
            conn,
            portal_id=portal_id,
            section_id=section["id"],
            course_id=section["course_id"],
            creator_user_id=user["id"],
            title=body.title,
            closes_at=_parse_dt(body.closes_at),
            max_score=body.max_score,
        )
    return {"id": portal_id, "message": "Portal created"}


@router.patch("/portals/{portal_id}")
async def update_portal(
    portal_id: int,
    body: UpdatePortalRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await assessment_repo.update_portal(
            conn,
            portal_id,
            title=body.title,
            description=body.description,
            opens_at=_parse_dt(body.opens_at) if body.opens_at else None,
            closes_at=_parse_dt(body.closes_at) if body.closes_at else None,
            max_score=body.max_score,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found")
    return {"message": "Portal updated"}


@router.delete("/portals/{portal_id}")
async def delete_portal(
    portal_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await assessment_repo.delete_portal(conn, portal_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found")
    return {"message": "Portal deleted"}


@router.get("/portals/{portal_id}")
async def get_portal(portal_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        portal = await assessment_repo.get_portal(conn, portal_id)
        if not portal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found")
        if not await assessment_repo.ensure_section_access(
            conn, portal["section_id"], user["id"], user["role_code"]
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
        submission = None
        if user["role_code"] == "student":
            submission = await assessment_repo.get_student_submission(
                conn, portal_id, user["id"]
            )
    return {**portal, "my_submission": submission}


@router.get("/portals/{portal_id}/submissions")
async def list_submissions(
    portal_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with get_connection() as conn:
        portal = await assessment_repo.get_portal(conn, portal_id)
        if not portal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found")
        items = await assessment_repo.list_submissions(conn, portal_id)
    return {"portal_id": portal_id, "items": items}


@router.post("/portals/{portal_id}/submissions")
async def submit(
    portal_id: int,
    body: SubmitAssessmentRequest,
    user: dict = Depends(require_roles("student")),
) -> dict:
    async with transaction() as conn:
        portal = await assessment_repo.get_portal(conn, portal_id)
        if not portal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found")
        sub_id = await assessment_repo.submit(
            conn,
            portal_id=portal_id,
            student_user_id=user["id"],
            file_id=body.file_id,
        )
    return {"id": sub_id, "message": "Submitted"}


@router.patch("/submissions/{submission_id}/grade")
async def grade_submission(
    submission_id: int,
    body: GradeSubmissionRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await assessment_repo.grade_submission(
            conn,
            submission_id=submission_id,
            grader_user_id=user["id"],
            score=body.score,
            feedback=body.feedback,
        )
        if ok:
            await grading_integration_service.on_submission_graded(
                conn,
                submission_id=submission_id,
                grader_user_id=user["id"],
                score=body.score,
                feedback=body.feedback,
            )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return {"message": "Graded"}


@router.get("/sections/{course_code}/{section_label}/grades")
async def list_grades(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        if not await assessment_repo.ensure_section_access(
            conn, section["id"], user["id"], user["role_code"]
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
        data = await grade_repo.list_gradebook_enriched(conn, section["id"])
        if user["role_code"] == "student":
            data["items"] = [i for i in data["items"] if i["id"] == user["id"]]
    return {"section_id": section["id"], **data}


@router.put("/sections/{course_code}/{section_label}/grades/{student_id}")
async def upsert_grade(
    course_code: str,
    section_label: str,
    student_id: int,
    body: UpsertGradeRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        await grade_repo.upsert_student_grade(
            conn,
            section_id=section["id"],
            student_user_id=student_id,
            recorder_user_id=user["id"],
            component_code=body.component_code,
            score=body.score,
            max_score=body.max_score,
            feedback=body.feedback,
        )
        if body.component_code.startswith("portal_"):
            try:
                portal_id = int(body.component_code.replace("portal_", ""))
                await grading_integration_service._update_grading_tasks(
                    conn, portal_id=portal_id, section_id=section["id"]
                )
            except Exception:
                pass
    return {"message": "Grade saved"}


@router.get("/sections/{course_code}/{section_label}/components")
async def list_grade_components(
    course_code: str,
    section_label: str,
    user: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        if not await assessment_repo.ensure_section_access(
            conn, section["id"], user["id"], user["role_code"]
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access")
        items = await grade_repo.list_components(conn, section["id"])
    return {"section_id": section["id"], "items": items}


@router.post("/sections/{course_code}/{section_label}/components")
async def create_grade_component(
    course_code: str,
    section_label: str,
    body: CreateGradeComponentRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await _resolve_section(conn, course_code, section_label)
        code = body.component_code
        if body.component_type == "ct" and not code:
            code = await grade_repo.next_ct_code(conn, section["id"])
        if not code:
            code = grade_repo._slug(body.label)
        try:
            comp_id = await grade_repo.create_component(
                conn,
                section_id=section["id"],
                component_type=body.component_type,
                label=body.label,
                component_code=code,
                max_score=body.max_score,
                weight_percent=body.weight_percent,
                creator_user_id=user["id"],
                sort_order=body.sort_order,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": comp_id, "component_code": code, "message": "Component created"}


@router.patch("/components/{component_id}")
async def update_grade_component(
    component_id: int,
    body: UpdateGradeComponentRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await grade_repo.update_component(
            conn,
            component_id,
            label=body.label,
            max_score=body.max_score,
            weight_percent=body.weight_percent,
            sort_order=body.sort_order,
            is_active=body.is_active,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
    return {"message": "Component updated"}


@router.delete("/components/{component_id}")
async def delete_grade_component(
    component_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await grade_repo.delete_component(conn, component_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")
    return {"message": "Component removed"}
