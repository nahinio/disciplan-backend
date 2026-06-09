from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.db.session import transaction
from app.repositories import academic_repo, chat_repo
from app.schemas.onboarding import CompleteOnboardingRequest

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/complete")
async def complete_onboarding(
    body: CompleteOnboardingRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        await academic_repo.update_profile(
            conn,
            user["id"],
            display_name=body.display_name,
            department_id=body.department_id,
        )

        role_code = user["role_code"]
        if body.role_code and body.role_code != role_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role is assigned automatically from your email",
            )

        linked = []
        for entry in body.sections:
            section = await academic_repo.find_section(
                conn, entry.course_code, entry.section_label
            )
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Section not found: {entry.course_code}::{entry.section_label}",
                )

            if role_code == "faculty":
                await academic_repo.assign_faculty(conn, section["id"], user["id"])
            else:
                await academic_repo.enroll_student(conn, section["id"], user["id"])

            await chat_repo.ensure_section_chat_member(
                conn,
                section_id=section["id"],
                user_id=user["id"],
                group_name=f"{entry.course_code} {entry.section_label} Chat",
                created_by_user_id=user["id"],
            )

            linked.append(
                {
                    "section_id": section["id"],
                    "section_key": f"{entry.course_code}::{entry.section_label}",
                }
            )

    return {
        "message": "Onboarding complete",
        "sections": linked,
        "display_name": body.display_name,
        "role_code": role_code,
    }
