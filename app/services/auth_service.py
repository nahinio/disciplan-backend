from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.config import get_settings
from app.db.session import transaction
from app.repositories import auth_repo, faculty_roster_repo, faculty_verification_repo
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    generate_otp,
    verify_password,
)


async def send_otp(email: str) -> dict:
    email = email.lower()
    if not email.endswith("@uiu.ac.bd"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only @uiu.ac.bd email addresses are allowed",
        )

    code = generate_otp()
    settings = get_settings()

    async with transaction() as conn:
        existing = await auth_repo.get_user_by_email(conn, email)
        if existing and existing["email_verified"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        await auth_repo.create_otp(conn, email, code)

    if settings.otp_demo_mode:
        print(f"[OTP] {email} -> {code}")

    return {"message": "Verification code sent", "expires_in_minutes": settings.otp_expire_minutes}


def _validate_signup_email(email: str) -> str:
    email = email.lower()
    if not email.endswith("@uiu.ac.bd"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only @uiu.ac.bd email addresses can register",
        )
    return email


async def register(
    *,
    email: str,
    password: str,
    display_name: str,
    department_id: int | None,
    role_code: str,
    message: str | None = None,
) -> dict:
    email = _validate_signup_email(email)

    if role_code not in ("student", "faculty"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    async with transaction() as conn:
        existing = await auth_repo.get_user_by_email(conn, email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        verification_pending = False
        account_status = "active"

        if role_code == "faculty":
            roster = await faculty_roster_repo.get_pending_by_email(conn, email)
            if roster:
                account_status = "active"
            else:
                account_status = "pending"
                verification_pending = True

        user_id = await auth_repo.create_user(
            conn,
            email=email,
            password=password,
            role_code=role_code,
            display_name=display_name,
            department_id=department_id,
            status_code=account_status,
        )

        if role_code == "faculty" and account_status == "active":
            await faculty_roster_repo.claim_roster_entry(conn, email=email, user_id=user_id)
        elif verification_pending:
            await faculty_verification_repo.create_request(
                conn,
                user_id=user_id,
                email=email,
                display_name=display_name,
                message=message,
            )

        access = create_access_token(user_id, role_code, email)
        refresh = create_refresh_token()
        settings = get_settings()
        expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
        await auth_repo.store_refresh_token(conn, user_id, refresh, expires)
        if account_status == "active":
            await auth_repo.touch_last_login(conn, user_id)

    if account_status == "active" and role_code in ("student", "faculty"):
        try:
            from app.services.lecture_task_service import generate_lecture_tasks_for_user
            await generate_lecture_tasks_for_user(user_id, role_code)
        except Exception:
            pass

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "verification_pending": verification_pending,
        "status_code": account_status,
    }


async def login(email: str, password: str) -> dict:
    email = email.lower()

    async with transaction() as conn:
        user = await auth_repo.get_user_by_email(conn, email)
        if user is None or not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if user["status_code"] == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been suspended. Contact an administrator.",
            )

        access = create_access_token(user["id"], user["role_code"], email)
        refresh = create_refresh_token()
        settings = get_settings()
        expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
        await auth_repo.store_refresh_token(conn, user["id"], refresh, expires)
        if user["status_code"] == "active":
            await auth_repo.touch_last_login(conn, user["id"])

    if user["status_code"] == "active" and user["role_code"] in ("student", "faculty"):
        try:
            from app.services.lecture_task_service import generate_lecture_tasks_for_user
            await generate_lecture_tasks_for_user(user["id"], user["role_code"])
        except Exception:
            pass

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "verification_pending": user["status_code"] == "pending",
        "status_code": user["status_code"],
    }


async def refresh_tokens(refresh_token: str) -> dict:
    async with transaction() as conn:
        row = await auth_repo.get_refresh_token_user(conn, refresh_token)
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        await auth_repo.revoke_refresh_token(conn, refresh_token)

        access = create_access_token(row["user_id"], row["role_code"], row["email"])
        new_refresh = create_refresh_token()
        settings = get_settings()
        expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
        await auth_repo.store_refresh_token(conn, row["user_id"], new_refresh, expires)

    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}
