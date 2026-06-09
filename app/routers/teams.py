from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user, require_roles
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, chat_repo, team_repo
from app.schemas.phase3 import (
    CreateTeamAnnouncementRequest,
    CreateTeamDateRequest,
    CreateTeamRequest,
    CreateTeamTaskRequest,
    FacultyAssignTeamRequest,
    GradeTeamRequest,
    InviteTeamMemberRequest,
    RespondInvitationRequest,
    UpdateTeamRequest,
)
from app.services import grading_integration_service

router = APIRouter(prefix="/teams", tags=["teams"])


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _require_member(conn, team_id: int, user_id: int) -> None:
    if not await team_repo._is_active_member(conn, team_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a team member")


@router.get("/by-section/{course_code}/{section_label}")
async def list_section_teams(
    course_code: str,
    section_label: str,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with get_connection() as conn:
        section = await academic_repo.find_section(conn, course_code, section_label)
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        items = await team_repo.list_section_teams(conn, section["id"])
    return {"section_id": section["id"], "items": items}


@router.get("")
async def list_teams(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        items = await team_repo.list_user_teams(
            conn,
            user["id"],
            faculty_assigned_only=user["role_code"] == "student",
        )
    return {"items": items}


@router.get("/invitations/pending")
async def list_pending_invitations(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        items = await team_repo.list_pending_invitations(conn, user["email"])
    return {"items": items}


@router.get("/{team_id}")
async def get_team(team_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        await _require_member(conn, team_id, user["id"])
        if user["role_code"] == "student" and not await team_repo.is_faculty_assigned(
            conn, team_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teams are assigned by faculty only",
            )
        team = await team_repo.get_team(conn, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.post("")
async def create_team(body: CreateTeamRequest, user: dict = Depends(get_current_user)) -> dict:
    if user["role_code"] == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot create teams. Teams are assigned by faculty.",
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Use POST /teams/faculty-assign to create section project teams.",
    )


@router.post("/{team_id}/invitations")
async def invite_member(
    team_id: int,
    body: InviteTeamMemberRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        team = await team_repo.get_team(conn, team_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        inv_id = await team_repo.invite_member(
            conn,
            team_id=team_id,
            invitee_email=body.email,
            invited_by_user_id=user["id"],
        )
    return {"id": inv_id, "message": "Invitation sent"}


@router.post("/invitations/{invitation_id}/respond")
async def respond_invitation(
    invitation_id: int,
    body: RespondInvitationRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        ok = await team_repo.respond_invitation(
            conn,
            invitation_id=invitation_id,
            user_id=user["id"],
            user_email=user["email"],
            accept=body.accept,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return {"message": "Invitation updated"}


@router.delete("/{team_id}/members/me")
async def leave_team(team_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with transaction() as conn:
        ok = await team_repo.leave_team(conn, team_id, user["id"])
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member")
    return {"message": "Left team"}


@router.delete("/{team_id}")
async def disband_team(
    team_id: int,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        await team_repo.disband_team(conn, team_id)
    return {"message": "Team disbanded"}


@router.post("/{team_id}/tasks")
async def create_task(
    team_id: int,
    body: CreateTeamTaskRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        await _require_member(conn, team_id, user["id"])
        task_id = await team_repo.create_task(
            conn,
            team_id=team_id,
            creator_user_id=user["id"],
            title=body.title,
            description=body.description,
            assignee_user_id=body.assignee_user_id,
            priority_code=body.priority_code,
            due_at=_parse_dt(body.due_at),
        )
    return {"id": task_id, "message": "Task created"}


@router.patch("/{team_id}/tasks/{task_id}")
async def toggle_task(
    team_id: int,
    task_id: int,
    completed: bool,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        await _require_member(conn, team_id, user["id"])
        ok = await team_repo.toggle_task(conn, team_id, task_id, completed)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"message": "Task updated"}


@router.post("/{team_id}/dates")
async def create_date(
    team_id: int,
    body: CreateTeamDateRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        await _require_member(conn, team_id, user["id"])
        date_id = await team_repo.create_date(
            conn,
            team_id=team_id,
            creator_user_id=user["id"],
            label=body.label,
            occurs_at=_parse_dt(body.occurs_at) or datetime.utcnow(),
        )
    return {"id": date_id, "message": "Date added"}


@router.post("/{team_id}/announcements")
async def create_announcement(
    team_id: int,
    body: CreateTeamAnnouncementRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        await _require_member(conn, team_id, user["id"])
        ann_id = await team_repo.create_announcement(
            conn,
            team_id=team_id,
            author_user_id=user["id"],
            title=body.title,
            body=body.body,
        )
    return {"id": ann_id, "message": "Announcement posted"}


@router.post("/{team_id}/pin")
async def pin_team(team_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with transaction() as conn:
        await _require_member(conn, team_id, user["id"])
        await team_repo.pin_team(conn, user["id"], team_id)
    return {"message": "Team pinned"}


@router.delete("/{team_id}/pin")
async def unpin_team(team_id: int, user: dict = Depends(get_current_user)) -> dict:
    async with transaction() as conn:
        await team_repo.unpin_team(conn, user["id"], team_id)
    return {"message": "Team unpinned"}


@router.post("/faculty-assign")
async def faculty_assign_team(
    body: FacultyAssignTeamRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        section = await academic_repo.find_section(
            conn, body.course_code, body.section_label
        )
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        team_id = await team_repo.faculty_assign_team(
            conn,
            course_id=section["course_id"],
            section_id=section["id"],
            name=body.name,
            faculty_user_id=user["id"],
            leader_user_id=body.leader_user_id,
            member_user_ids=body.member_user_ids,
        )
        member_ids = await team_repo.list_team_member_ids(conn, team_id)
        await chat_repo.create_team_group(
            conn,
            team_id=team_id,
            name=f"{body.name} Chat",
            created_by_user_id=user["id"],
            member_user_ids=member_ids,
        )
    return {"id": team_id, "message": "Team assigned"}


@router.patch("/{team_id}")
async def update_team(
    team_id: int,
    body: UpdateTeamRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        ok = await team_repo.update_team(
            conn,
            team_id,
            name=body.name,
            leader_user_id=body.leader_user_id,
            add_member_user_ids=body.add_member_user_ids,
            remove_member_user_ids=body.remove_member_user_ids,
        )
        if ok and (body.add_member_user_ids or body.leader_user_id):
            member_ids = await team_repo.list_team_member_ids(conn, team_id)
            team = await team_repo.get_team(conn, team_id)
            if team:
                await chat_repo.create_team_group(
                    conn,
                    team_id=team_id,
                    name=f"{team['team_name']} Chat",
                    created_by_user_id=user["id"],
                    member_user_ids=member_ids,
                )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return {"message": "Team updated"}


@router.post("/{team_id}/grade")
async def grade_team(
    team_id: int,
    body: GradeTeamRequest,
    user: dict = Depends(require_roles("faculty", "admin")),
) -> dict:
    async with transaction() as conn:
        team = await team_repo.get_team(conn, team_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        section = await fetch_section_for_team(conn, team)
        if not section:
            raise HTTPException(status_code=400, detail="Team has no section")
        member_ids = await team_repo.list_team_member_ids(conn, team_id)
        await grading_integration_service.on_team_graded(
            conn,
            team_id=team_id,
            section_id=section["id"],
            grader_user_id=user["id"],
            score=body.score,
            max_score=body.max_score,
            label=body.label,
            member_user_ids=member_ids,
            feedback=body.feedback,
        )
    return {"message": "Team graded"}


async def fetch_section_for_team(conn, team: dict) -> dict | None:
    if not team.get("section"):
        return None
    return await academic_repo.find_section(
        conn, team["course_code"], team["section"]
    )
