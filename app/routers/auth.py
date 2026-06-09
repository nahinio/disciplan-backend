from fastapi import APIRouter, Query

from app.db.session import get_connection
from app.repositories import faculty_roster_repo
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    SendOtpRequest,
    SendOtpResponse,
    TokenResponse,
    VerifyOtpRequest,
)
from app.schemas.common import MessageResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/send", response_model=SendOtpResponse)
async def send_otp(body: SendOtpRequest) -> SendOtpResponse:
    result = await auth_service.send_otp(body.email)
    return SendOtpResponse(**result)


@router.post("/otp/verify", response_model=MessageResponse)
async def verify_otp(body: VerifyOtpRequest) -> MessageResponse:
    from app.db.session import transaction
    from app.repositories import auth_repo

    async with transaction() as conn:
        ok = await auth_repo.verify_otp(conn, body.email.lower(), body.code)
    if not ok:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    return MessageResponse(message="OTP verified")


@router.get("/check-faculty-roster")
async def check_faculty_roster(email: str = Query(..., min_length=3)) -> dict:
    async with get_connection() as conn:
        entry = await faculty_roster_repo.get_pending_by_email(conn, email.lower())
    return {"on_roster": entry is not None}


@router.get("/signup-role")
async def signup_role(email: str = Query(..., min_length=3)) -> dict:
    """Resolve signup role from faculty roster (pending entries only)."""
    async with get_connection() as conn:
        entry = await faculty_roster_repo.get_pending_by_email(conn, email.lower())
    if entry:
        return {
            "role_code": "faculty",
            "suggested_name": entry.get("display_name"),
            "on_roster": True,
        }
    return {"role_code": "student", "on_roster": False}


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest) -> TokenResponse:
    result = await auth_service.register(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        department_id=body.department_id,
        role_code=body.role_code,
        message=body.message,
    )
    return TokenResponse(**result)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    result = await auth_service.login(body.email, body.password)
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest) -> TokenResponse:
    result = await auth_service.refresh_tokens(body.refresh_token)
    return TokenResponse(**result)
