from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.session import fetch_one, get_connection
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = int(payload["sub"])

    async with get_connection() as conn:
        user = await fetch_one(
            conn,
            """
            SELECT u.id, u.email, u.email_verified, r.code AS role_code, us.code AS status_code,
                   up.display_name, up.department_id
            FROM users u
            INNER JOIN roles r ON r.id = u.role_id
            INNER JOIN user_statuses us ON us.id = u.status_id
            LEFT JOIN user_profiles up ON up.user_id = u.id
            WHERE u.id = %s
            """,
            (user_id,),
        )

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user["status_code"] == "suspended":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")

    return user


def require_roles(*allowed: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role_code"] not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker
