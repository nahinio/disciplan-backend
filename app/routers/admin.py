from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from app.dependencies.auth import require_roles
from app.db.session import get_connection, transaction
from app.repositories import (
    academic_repo,
    admin_repo,
    auth_repo,
    blog_repo,
    chat_repo,
    faculty_roster_repo,
    faculty_verification_repo,
    forum_repo,
    gamification_repo,
    practice_repo,
    enrollment_repo,
    report_repo,
)
from app.schemas.enrollment import AdminEnrollStudentBody
from app.schemas.phase3 import (
    AdjustPointsRequest,
    AdminCreateCourseRequest,
    AdminCreateDepartmentRequest,
    AdminUpdateDepartmentRequest,
    AdminCreateSectionRequest,
    AdminFacultyRosterRequest,
    AdminGlobalAnnouncementRequest,
    AdminUpdateAnnouncementRequest,
    AdminUpdateSectionRequest,
    AdminDeleteUserRequest,
    AdminUpdateUserRequest,
    AwardBadgeRequest,
    ForumMergeRequest,
    ForumMoveRequest,
    AdminUpdateTopicRequest,
    ResolveContentReportRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        items = await admin_repo.list_users(conn)
    return {"items": items}


@router.get("/faculty-roster")
async def list_faculty_roster(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        items = await faculty_roster_repo.list_roster(conn)
    return {"items": items}


@router.post("/faculty-roster", status_code=status.HTTP_201_CREATED)
async def add_faculty_roster(
    body: AdminFacultyRosterRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    email = body.email.strip().lower()
    if not email.endswith("@uiu.ac.bd"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faculty email must be a @uiu.ac.bd address",
        )

    async with transaction() as conn:
        existing_user = await auth_repo.get_user_by_email(conn, email)
        if existing_user:
            if existing_user.get("role_code") == "faculty":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email already belongs to a faculty account",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered as a student account",
            )

        pending = await faculty_roster_repo.get_pending_by_email(conn, email)
        if pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already on the faculty roster",
            )

        roster_id = await faculty_roster_repo.add_roster_entry(
            conn,
            email=email,
            display_name=body.display_name,
            invited_by_user_id=admin["id"],
        )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=roster_id,
            details={"email": email, "display_name": body.display_name, "action": "faculty_roster_add"},
            ip_address=request.client.host if request and request.client else None,
        )

    return {"id": roster_id, "email": email, "display_name": body.display_name, "status": "pending"}


@router.delete("/faculty-roster/{roster_id}")
async def remove_faculty_roster(
    roster_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        removed = await faculty_roster_repo.delete_pending(conn, roster_id)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Faculty roster entry not found or already registered",
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=roster_id,
            details={"action": "faculty_roster_remove"},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Faculty removed from roster"}


@router.get("/students/enrollments-summary")
async def list_students_enrollment_summary(
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with get_connection() as conn:
        items = await enrollment_repo.list_students_enrollment_summary(conn)
    return {"items": items}


@router.get("/users/{user_id}/enrollments")
async def list_user_enrollments(
    user_id: int,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with get_connection() as conn:
        target = await admin_repo.get_user_admin(conn, user_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        items = await enrollment_repo.list_student_enrollments(conn, user_id)
    return {"items": items, "user": target}


@router.post("/users/{user_id}/enrollments", status_code=status.HTTP_201_CREATED)
async def admin_enroll_user(
    user_id: int,
    body: AdminEnrollStudentBody,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    try:
        async with transaction() as conn:
            section = await enrollment_repo.admin_enroll_student(
                conn,
                student_user_id=user_id,
                course_code=body.course_code.strip().upper(),
                section_label=body.section_label.strip().upper(),
                actor_user_id=admin["id"],
            )
            await admin_repo.log_action(
                conn,
                actor_user_id=admin["id"],
                action_code="user_suspend",
                entity_type_code="user",
                entity_id=user_id,
                details={
                    "action": "admin_enroll_student",
                    "course_code": body.course_code,
                    "section_label": body.section_label,
                },
                ip_address=request.client.host if request and request.client else None,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "message": "Student enrolled",
        "section_id": section["id"],
        "section_key": f"{body.course_code}::{body.section_label}",
    }


@router.delete("/users/{user_id}/enrollments/{course_code}/{section_label}")
async def admin_drop_user_enrollment(
    user_id: int,
    course_code: str,
    section_label: str,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    try:
        async with transaction() as conn:
            ok = await enrollment_repo.admin_drop_student(
                conn,
                student_user_id=user_id,
                course_code=course_code.strip().upper(),
                section_label=section_label.strip().upper(),
            )
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Enrollment not found",
                )
            await admin_repo.log_action(
                conn,
                actor_user_id=admin["id"],
                action_code="user_suspend",
                entity_type_code="user",
                entity_id=user_id,
                details={
                    "action": "admin_drop_student",
                    "course_code": course_code,
                    "section_label": section_label,
                },
                ip_address=request.client.host if request and request.client else None,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"message": "Enrollment removed"}


@router.post("/enrollments/import")
async def import_enrollments_csv(
    file: UploadFile = File(...),
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a .csv file",
        )
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must be UTF-8 encoded",
        ) from exc
    try:
        async with transaction() as conn:
            result = await enrollment_repo.import_enrollments_from_csv(
                conn, content=content, actor_user_id=admin["id"]
            )
            await admin_repo.log_action(
                conn,
                actor_user_id=admin["id"],
                action_code="user_suspend",
                entity_type_code="user",
                entity_id=None,
                details={"action": "enrollments_csv_import", **result},
                ip_address=request.client.host if request and request.client else None,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.get("/enrollment-requests")
async def list_enrollment_requests(
    status: str | None = Query(default="pending"),
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with get_connection() as conn:
        items = await enrollment_repo.list_requests_admin(conn, status=status)
    return {"items": items}


@router.post("/enrollment-requests/{request_id}/approve")
async def approve_enrollment_request(
    request_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        req = await enrollment_repo.approve_request(
            conn, request_id=request_id, reviewer_id=admin["id"]
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enrollment request not found or already reviewed",
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=req["student_user_id"],
            details={"action": "enrollment_request_approve", "request_id": request_id},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Enrollment approved", "request": req}


@router.post("/enrollment-requests/{request_id}/reject")
async def reject_enrollment_request(
    request_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        req = await enrollment_repo.reject_request(
            conn, request_id=request_id, reviewer_id=admin["id"]
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enrollment request not found or already reviewed",
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=req["student_user_id"],
            details={"action": "enrollment_request_reject", "request_id": request_id},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Enrollment request rejected"}


@router.delete("/enrollment-requests/{request_id}")
async def delete_enrollment_request(
    request_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        ok = await enrollment_repo.delete_request(conn, request_id)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending request not found",
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=None,
            details={"action": "enrollment_request_delete", "request_id": request_id},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Request deleted"}


@router.get("/faculty-verification-requests")
async def list_faculty_verification_requests(
    status: str | None = Query(default="pending"),
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with get_connection() as conn:
        items = await faculty_verification_repo.list_requests(conn, status=status)
    return {"items": items}


@router.post("/faculty-verification-requests/{request_id}/approve")
async def approve_faculty_verification(
    request_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        req = await faculty_verification_repo.approve_request(
            conn, request_id=request_id, reviewer_id=admin["id"]
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification request not found or already reviewed",
            )
        await faculty_roster_repo.ensure_claimed(
            conn,
            email=req["email"],
            display_name=req["display_name"],
            user_id=req["user_id"],
            invited_by_user_id=admin["id"],
        )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=req["user_id"],
            details={"action": "faculty_verification_approve", "request_id": request_id},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Faculty verification approved"}


@router.post("/faculty-verification-requests/{request_id}/reject")
async def reject_faculty_verification(
    request_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        req = await faculty_verification_repo.reject_request(
            conn, request_id=request_id, reviewer_id=admin["id"]
        )
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification request not found or already reviewed",
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=req["user_id"],
            details={"action": "faculty_verification_reject", "request_id": request_id},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Faculty verification rejected"}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: AdminUpdateUserRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        await admin_repo.update_user(
            conn,
            user_id,
            role_code=body.role_code,
            status_code=body.status_code,
            display_name=body.display_name,
            department_id=body.department_id,
        )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="user_suspend",
            entity_type_code="user",
            entity_id=user_id,
            details=body.model_dump(exclude_none=True),
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "User updated"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    body: AdminDeleteUserRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    async with transaction() as conn:
        target = await admin_repo.get_user_admin(conn, user_id)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if target["role_code"] == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin accounts cannot be deleted from the user directory",
            )

        if body.confirm_email.strip().lower() != target["email"].lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation email does not match",
            )

        if body.delete_faculty_sections and target["role_code"] != "faculty":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section deletion only applies to faculty accounts",
            )

        deleted = await admin_repo.delete_user(
            conn,
            user_id,
            delete_faculty_sections=body.delete_faculty_sections,
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="content_delete",
            entity_type_code="user",
            entity_id=user_id,
            details={
                "action": "user_delete",
                "email": deleted["email"],
                "role": deleted["role_code"],
                "delete_faculty_sections": body.delete_faculty_sections,
            },
            ip_address=request.client.host if request and request.client else None,
        )

    return {"message": "User deleted permanently"}


@router.post("/departments")
async def create_department(
    body: AdminCreateDepartmentRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        try:
            dept = await admin_repo.create_department(
                conn, name=body.name, code=body.code
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="course_create",
            entity_type_code=None,
            entity_id=dept["id"],
            details={"department_code": dept["code"], "department_name": dept["name"]},
            ip_address=request.client.host if request and request.client else None,
        )
    return {**dept, "message": "Department created"}


@router.patch("/departments/{department_id}")
async def update_department(
    department_id: int,
    body: AdminUpdateDepartmentRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        dept = await admin_repo.update_department(
            conn, department_id, name=body.name
        )
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="course_create",
            entity_type_code=None,
            entity_id=dept["id"],
            details={"department_code": dept["code"], "department_name": dept["name"]},
            ip_address=request.client.host if request and request.client else None,
        )
    return {**dept, "message": "Department updated"}


@router.delete("/departments/{department_id}")
async def delete_department(
    department_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        result = await admin_repo.delete_department(conn, department_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="course_create",
            entity_type_code=None,
            entity_id=result["id"],
            details={
                "department_code": result["code"],
                "department_name": result["name"],
                "courses_deleted": result["courses_deleted"],
                "deleted": True,
            },
            ip_address=request.client.host if request and request.client else None,
        )
    return {
        "message": "Department deleted",
        "courses_deleted": result["courses_deleted"],
    }


@router.post("/courses")
async def create_course(
    body: AdminCreateCourseRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        course_id = await admin_repo.create_course(
            conn,
            code=body.code,
            title=body.title,
            department_id=body.department_id,
            credit_hours=body.credit_hours,
            has_project=body.has_project,
            course_type_code=body.course_type_code,
        )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="course_create",
            entity_type_code=None,
            entity_id=course_id,
            details={"code": body.code},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"id": course_id, "message": "Course created"}


@router.get("/sections")
async def list_sections(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        items = await admin_repo.list_sections(conn)
    return {"items": items}


@router.post("/sections")
async def create_section(
    body: AdminCreateSectionRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, body.course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        try:
            section_id = await admin_repo.create_section(
                conn,
                course_id=course["id"],
                section_label=body.section_label,
                room=body.room,
                faculty_user_id=body.faculty_user_id,
                schedule_key=body.schedule_key,
                starts_at=body.starts_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if body.faculty_user_id:
            await chat_repo.ensure_section_chat_member(
                conn,
                section_id=section_id,
                user_id=body.faculty_user_id,
                group_name=f"{body.course_code} {body.section_label} Chat",
                created_by_user_id=body.faculty_user_id,
            )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="section_create",
            entity_type_code="section",
            entity_id=section_id,
            details={"course_code": body.course_code, "section": body.section_label},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"id": section_id, "message": "Section created"}


@router.patch("/sections/{section_id}")
async def update_section(
    section_id: int,
    body: AdminUpdateSectionRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    async with transaction() as conn:
        try:
            ok = await admin_repo.update_section(
                conn,
                section_id,
                room=updates.get("room"),
                faculty_user_id=updates["faculty_user_id"]
                if "faculty_user_id" in updates
                else ...,
                schedule_key=updates.get("schedule_key"),
                starts_at=updates.get("starts_at"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="section_create",
            entity_type_code="section",
            entity_id=section_id,
            details=body.model_dump(exclude_none=True),
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Section updated"}


@router.delete("/sections/{section_id}")
async def delete_section(
    section_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        ok = await admin_repo.delete_section(conn, section_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="section_create",
            entity_type_code="section",
            entity_id=section_id,
            details={"deleted": True},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Section and all related data removed"}


@router.get("/announcements")
async def list_announcements(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        items = await admin_repo.list_global_announcements(conn)
    return {"items": items}


@router.patch("/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: int,
    body: AdminUpdateAnnouncementRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        ok = await admin_repo.update_global_announcement(
            conn,
            announcement_id,
            title=body.title,
            body=body.body,
            is_active=body.is_active,
            scheduled_for=body.scheduled_for,
        )
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="announcement_post",
            entity_type_code="announcement",
            entity_id=announcement_id,
            details=body.model_dump(exclude_none=True),
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Announcement updated"}


@router.delete("/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: int,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        ok = await admin_repo.delete_global_announcement(conn, announcement_id)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="announcement_post",
            entity_type_code="announcement",
            entity_id=announcement_id,
            details={"deleted": True},
            ip_address=request.client.host if request and request.client else None,
        )
    return {"message": "Announcement deleted"}


@router.post("/announcements")
async def create_announcement(
    body: AdminGlobalAnnouncementRequest,
    admin: dict = Depends(require_roles("admin")),
    request: Request = None,
) -> dict:
    async with transaction() as conn:
        ann_id = await admin_repo.create_global_announcement(
            conn,
            author_user_id=admin["id"],
            title=body.title,
            body=body.body,
            is_active=body.is_active,
            scheduled_for=body.scheduled_for,
            target_audience=body.target_audience,
        )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="announcement_post",
            entity_type_code="announcement",
            entity_id=ann_id,
            ip_address=request.client.host if request and request.client else None,
        )
    return {"id": ann_id, "message": "Announcement created"}


@router.get("/audit-logs")
async def list_audit_logs(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        items = await admin_repo.list_audit_logs(conn)
    return {"items": items}


@router.get("/reports/activity")
async def activity_report(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        return await admin_repo.activity_summary(conn)


@router.post("/users/{user_id}/points/adjust")
async def adjust_points(
    user_id: int,
    body: AdjustPointsRequest,
    admin: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        await gamification_repo.admin_adjust_points(
            conn, user_id=user_id, delta=body.delta, reason_code=body.reason or "admin_adjustment"
        )
        await admin_repo.log_action(
            conn,
            actor_user_id=admin["id"],
            action_code="grade_record",
            entity_type_code="user",
            entity_id=user_id,
            details={"delta": body.delta},
        )
    return {"message": "Points adjusted"}


@router.post("/users/badges")
async def award_badge(
    body: AwardBadgeRequest,
    admin: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        badge_id = await gamification_repo.award_badge(
            conn,
            user_id=body.user_id,
            badge_code=body.badge_code,
            awarded_by_user_id=admin["id"],
        )
    return {"id": badge_id, "message": "Badge awarded"}


@router.patch("/courses/{course_code}")
async def update_course(
    course_code: str,
    title: str | None = None,
    is_active: bool | None = None,
    has_project: bool | None = None,
    course_type_code: str | None = Query(
        default=None,
        pattern="^(theory|lab)$",
    ),
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        ok = await admin_repo.update_course(
            conn,
            course["id"],
            title=title,
            is_active=is_active,
            has_project=has_project,
            course_type_code=course_type_code,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return {"message": "Course updated"}


@router.get("/blogs")
async def admin_list_blogs(
    _: dict = Depends(require_roles("admin")),
    course_code: str | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    verified_only: bool = Query(default=False),
    moderation_only: bool = Query(default=False),
    limit: int = Query(default=100, le=200),
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
        items = await blog_repo.list_posts_admin(
            conn,
            course_id=course_id,
            topic_id=topic_id,
            q=q,
            verified_only=verified_only,
            moderation_only=moderation_only,
            limit=limit,
        )
    return {"items": items}


@router.delete("/blogs/posts/{post_id}")
async def admin_delete_blog(post_id: int, _: dict = Depends(require_roles("admin"))) -> dict:
    async with transaction() as conn:
        ok = await blog_repo.delete_post(conn, post_id, is_admin=True)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return {"message": "Post removed"}


@router.post("/forum/threads/{thread_id}/move")
async def move_forum_thread(
    thread_id: int,
    body: ForumMoveRequest,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, body.target_course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        ok = await forum_repo.move_thread(conn, thread_id, course["id"])
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return {"message": "Thread moved"}


@router.post("/forum/threads/{thread_id}/merge")
async def merge_forum_threads(
    thread_id: int,
    body: ForumMergeRequest,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        ok = await forum_repo.merge_threads(conn, thread_id, body.target_thread_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Threads not found")
    return {"message": "Threads merged"}


@router.delete("/forum/threads/{thread_id}")
async def delete_forum_thread(
    thread_id: int, _: dict = Depends(require_roles("admin"))
) -> dict:
    async with transaction() as conn:
        ok = await forum_repo.delete_thread(conn, thread_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return {"message": "Thread removed"}


@router.delete("/forum/replies/{reply_id}")
async def admin_delete_forum_reply(
    reply_id: int, _: dict = Depends(require_roles("admin"))
) -> dict:
    async with transaction() as conn:
        ok = await forum_repo.delete_reply(conn, reply_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found")
    return {"message": "Reply removed"}


@router.delete("/blogs/comments/{comment_id}")
async def admin_delete_blog_comment(
    comment_id: int, _: dict = Depends(require_roles("admin"))
) -> dict:
    async with transaction() as conn:
        ok = await blog_repo.delete_comment(conn, comment_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return {"message": "Comment removed"}


@router.get("/catalog/content-stats")
async def catalog_content_stats(_: dict = Depends(require_roles("admin"))) -> dict:
    async with get_connection() as conn:
        items = await admin_repo.catalog_content_stats(conn)
    return {"items": items}


@router.patch("/courses/{course_code}/topics/{topic_id}")
async def admin_update_topic(
    course_code: str,
    topic_id: int,
    body: AdminUpdateTopicRequest,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        ok = await practice_repo.update_topic(
            conn,
            topic_id=topic_id,
            course_id=course["id"],
            title=body.title,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return {"message": "Topic updated"}


@router.get("/courses/{course_code}/topics/{topic_id}/delete-impact")
async def admin_topic_delete_impact(
    course_code: str,
    topic_id: int,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with get_connection() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        impact = await practice_repo.topic_delete_impact(
            conn, topic_id=topic_id, course_id=course["id"]
        )
    if not impact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return {
        "title": impact["title"],
        "blog_count": int(impact["blog_count"] or 0),
        "problem_count": int(impact["problem_count"] or 0),
    }


@router.delete("/courses/{course_code}/topics/{topic_id}")
async def admin_delete_topic(
    course_code: str,
    topic_id: int,
    _: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        course = await academic_repo.get_course_by_code(conn, course_code)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        result = await practice_repo.delete_topic_cascade(
            conn, topic_id=topic_id, course_id=course["id"]
        )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return {
        "message": "Topic deleted",
        "blogs_deleted": result["blogs_deleted"],
        "problems_deleted": result["problems_deleted"],
    }


@router.get("/content-reports")
async def list_content_reports(
    _: dict = Depends(require_roles("admin")),
    status: str = Query(default="open", pattern="^(open|reviewed|resolved|dismissed)$"),
    entity_type: str | None = Query(
        default=None,
        pattern="^(blog_post|blog_comment|forum_thread|forum_reply)$",
    ),
    entity_types: str | None = Query(
        default=None,
        description="Comma-separated entity type codes (e.g. blog_comment,forum_reply)",
    ),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    codes: list[str] | None = None
    if entity_types:
        codes = [c.strip() for c in entity_types.split(",") if c.strip()]
    async with get_connection() as conn:
        items = await report_repo.list_reports_admin(
            conn,
            status_code=status,
            entity_type_code=entity_type if not codes else None,
            entity_type_codes=codes,
            limit=limit,
            offset=offset,
        )
    return {"items": items}


@router.post("/content-reports/{report_id}/resolve")
async def resolve_content_report(
    report_id: int,
    body: ResolveContentReportRequest,
    admin: dict = Depends(require_roles("admin")),
) -> dict:
    async with transaction() as conn:
        report = await report_repo.get_report(conn, report_id)
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        if body.delete_content:
            entity_type = str(report["entity_type_code"])
            entity_id = int(report["entity_id"])
            deleted = False
            if entity_type == "blog_post":
                deleted = await blog_repo.delete_post(conn, entity_id, is_admin=True)
            elif entity_type == "blog_comment":
                deleted = await blog_repo.delete_comment(conn, entity_id)
            elif entity_type == "forum_thread":
                deleted = await forum_repo.delete_thread(conn, entity_id)
            elif entity_type == "forum_reply":
                deleted = await forum_repo.delete_reply(conn, entity_id)
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Content already removed",
                )

        ok = await report_repo.resolve_report(
            conn,
            report_id,
            resolver_user_id=admin["id"],
            status_code=body.action,
        )
        if ok and body.delete_content and report.get("reporter_user_id"):
            from app.services import gamification_service

            await gamification_service.on_moderation_approved(
                conn,
                reporter_user_id=int(report["reporter_user_id"]),
                report_id=report_id,
            )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return {"message": f"Report {body.action}"}


