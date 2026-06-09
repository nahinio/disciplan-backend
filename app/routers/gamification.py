import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.db.session import get_connection
from app.repositories import gamification_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/me")
async def gamification_me(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role_code") in ("faculty", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gamification is for student accounts only",
        )
    async with get_connection() as conn:
        data = await gamification_repo.get_gamification_me(conn, user["id"])
    return data


@router.get("/me/achievements")
async def gamification_achievements(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role_code") in ("faculty", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Gamification is for student accounts only",
        )
    async with get_connection() as conn:
        items = await gamification_repo.list_achievement_ladder(conn, user["id"])
    return {"items": items}


@router.get("/leaderboard")
async def leaderboard(
    user: dict = Depends(get_current_user),
    period: str = Query(default="all_time", pattern="^(all_time|today)$"),
    limit: int = Query(default=100, le=200),
) -> dict:
    # Faculty accounts do not participate in gamification UI.
    if user.get("role_code") == "faculty":
        return {"period": period, "items": [], "my_rank": None, "badges": []}

    try:
        async with get_connection() as conn:
            items = await gamification_repo.get_leaderboard(conn, period=period, limit=limit)
            my_rank = await gamification_repo.get_user_rank(conn, user["id"], period=period)
            badges = await gamification_repo.list_user_badges(conn, user["id"])
        return {"period": period, "items": items, "my_rank": my_rank, "badges": badges}
    except Exception:
        logger.exception("Leaderboard query failed for period=%s", period)
        return {"period": period, "items": [], "my_rank": None, "badges": []}


@router.get("/me/points/history")
async def point_history(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        items = await gamification_repo.list_point_history(conn, user["id"])
    return {"items": items}
