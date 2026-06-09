from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.db.session import execute, fetch_one, get_connection, transaction
from app.repositories import academic_repo, admin_repo, gamification_repo, profile_repo
from app.schemas.academic import DeleteAccountRequest, UpdatePreferencesRequest, UpdateProfileRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        profile = await fetch_one(
            conn,
            """
            SELECT
                u.id, u.email, u.email_verified, u.created_at, u.last_login_at,
                r.code AS role_code,
                us.code AS status_code,
                up.display_name, up.department_id, up.bio,
                up.avatar_file_id, up.avatar_preset,
                af.secure_url AS avatar_url,
                d.code AS department_code, d.name AS department_name,
                ug.total_points, gt.code AS tier_code, gt.label AS tier_label,
                pref.theme, pref.notify_academic, pref.notify_teams,
                pref.notify_system, pref.notify_messages
            FROM users u
            INNER JOIN roles r ON r.id = u.role_id
            INNER JOIN user_statuses us ON us.id = u.status_id
            LEFT JOIN user_profiles up ON up.user_id = u.id
            LEFT JOIN files af ON af.id = up.avatar_file_id AND af.deleted_at IS NULL
            LEFT JOIN departments d ON d.id = up.department_id
            LEFT JOIN user_gamification ug ON ug.user_id = u.id
            LEFT JOIN gamification_tiers gt ON gt.id = ug.tier_id
            LEFT JOIN user_preferences pref ON pref.user_id = u.id
            WHERE u.id = %s
            """,
            (user["id"],),
        )
        sections = await academic_repo.list_user_sections(
            conn, user["id"], profile["role_code"] if profile else user["role_code"]
        )
        if profile and profile.get("role_code") == "student":
            tier_info = await gamification_repo.get_tier_info(conn, user["id"])
            if tier_info:
                profile["next_tier_points"] = tier_info.get("next_tier_points")
                profile["next_tier_label"] = tier_info.get("next_tier_label")
            streaks = await gamification_repo.list_user_streaks(conn, user["id"])
            profile["streaks"] = streaks
    if profile:
        profile["sections"] = sections
    return profile or user


@router.get("/{user_id}/profile")
async def get_user_profile(
    user_id: int,
    _viewer: dict = Depends(get_current_user),
) -> dict:
    async with get_connection() as conn:
        profile = await profile_repo.get_public_student_profile(conn, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found",
        )
    return profile


@router.patch("/me/profile")
async def update_profile(
    body: UpdateProfileRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    async with transaction() as conn:
        await academic_repo.update_profile(
            conn,
            user["id"],
            display_name=updates.get("display_name"),
            department_id=updates.get("department_id"),
            avatar_file_id=updates["avatar_file_id"] if "avatar_file_id" in updates else ...,
            avatar_preset=updates["avatar_preset"] if "avatar_preset" in updates else ...,
        )
        if "bio" in updates:
            await execute(
                conn,
                "UPDATE user_profiles SET bio = %s WHERE user_id = %s",
                (updates["bio"], user["id"]),
            )
    return {"message": "Profile updated"}


@router.patch("/me/preferences")
async def update_preferences(
    body: UpdatePreferencesRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    fields = []
    params: list = []
    if body.theme is not None:
        fields.append("theme = %s")
        params.append(body.theme)
    if body.notify_academic is not None:
        fields.append("notify_academic = %s")
        params.append(int(body.notify_academic))
    if body.notify_teams is not None:
        fields.append("notify_teams = %s")
        params.append(int(body.notify_teams))
    if body.notify_system is not None:
        fields.append("notify_system = %s")
        params.append(int(body.notify_system))
    if body.notify_messages is not None:
        fields.append("notify_messages = %s")
        params.append(int(body.notify_messages))

    if not fields:
        return {"message": "No changes"}

    params.append(user["id"])
    async with transaction() as conn:
        await execute(
            conn,
            f"UPDATE user_preferences SET {', '.join(fields)} WHERE user_id = %s",
            tuple(params),
        )
    return {"message": "Preferences updated"}


@router.delete("/me")
async def delete_my_account(
    body: DeleteAccountRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    if body.confirm_email.strip().lower() != user["email"].lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match",
        )
    if user["role_code"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin accounts cannot be self-deleted. Contact another administrator.",
        )

    async with transaction() as conn:
        deleted = await admin_repo.delete_user(
            conn,
            user["id"],
            delete_faculty_sections=user["role_code"] == "faculty",
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {"message": "Account deleted permanently"}
