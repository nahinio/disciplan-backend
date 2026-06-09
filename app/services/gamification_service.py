"""Award reputation points on community and planner actions."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pymysql

from app.repositories import gamification_repo, task_planner_repo

POINT_DAILY_BLUEPRINT = 15
POINT_BLUEPRINT_STREAK_3 = 40
POINT_WEEKLY_ACTIVITY = 25
POINT_BLOG_UPVOTE = 2
POINT_BLOG_MILESTONE_50 = 50
POINT_BLOG_MILESTONE_100 = 100
POINT_BLOG_PUBLISH = 20
POINT_FACULTY_ENDORSED = 30
POINT_DOUBT_ANSWER = 5
POINT_MODERATION = 50
POINT_SPEEDRUNNER = 10

BLOG_UPVOTE_CAP_PER_POST = 30
SPEEDRUNNER_DAILY_CAP = 3


async def _award(
    conn: pymysql.Connection,
    *,
    user_id: int,
    delta: int,
    reason_code: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
    cap_key: str | None = None,
    cap_max: int = 1,
    season_key: str = "",
) -> list[dict[str, Any]]:
    if cap_key is not None:
        allowed = await gamification_repo.try_consume_cap(
            conn,
            reason_code=reason_code,
            reference_key=cap_key,
            season_key=season_key,
            max_awards=cap_max,
        )
        if not allowed:
            return []
    await gamification_repo.award_points(
        conn,
        user_id=user_id,
        delta=delta,
        reason_code=reason_code,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    return await gamification_repo.check_and_unlock_achievements(conn, user_id)


async def record_activity_day(
    conn: pymysql.Connection, user_id: int, activity_date: date | None = None
) -> list[dict[str, Any]]:
    """Track qualifying daily activity for weekly streak bonus."""
    activity_date = activity_date or date.today()
    streak = await gamification_repo.update_streak(
        conn,
        user_id=user_id,
        streak_code="weekly_activity",
        activity_date=activity_date,
    )
    unlocked: list[dict[str, Any]] = []
    if streak["current_count"] == 7:
        unlocked = await _award(
            conn,
            user_id=user_id,
            delta=POINT_WEEKLY_ACTIVITY,
            reason_code="weekly_activity_streak",
            cap_key=f"user:{user_id}:weekly7",
            season_key=str(activity_date),
        )
    return unlocked


async def evaluate_daily_blueprint(
    conn: pymysql.Connection,
    user_id: int,
    target_date: date | None = None,
) -> list[dict[str, Any]]:
    """Award daily blueprint completion when all non-skipped tasks for the day are done."""
    target_date = target_date or date.today()
    tasks = await task_planner_repo.list_tasks_for_day(conn, user_id, target_date=target_date)
    if not tasks:
        return []

    for task in tasks:
        if not int(task.get("is_completed") or 0):
            return []
        pct = int(task.get("completion_percent") or 0)
        if pct < 100:
            return []

    unlocked = await _award(
        conn,
        user_id=user_id,
        delta=POINT_DAILY_BLUEPRINT,
        reason_code="daily_blueprint_complete",
        cap_key=f"user:{user_id}:blueprint",
        season_key=str(target_date),
    )

    streak = await gamification_repo.update_streak(
        conn,
        user_id=user_id,
        streak_code="iron_will",
        activity_date=target_date,
    )
    if streak["current_count"] == 3:
        streak_bonus = await _award(
            conn,
            user_id=user_id,
            delta=POINT_BLUEPRINT_STREAK_3,
            reason_code="blueprint_streak_3",
            cap_key=f"user:{user_id}:iron3",
            season_key=str(target_date),
        )
        unlocked.extend(streak_bonus)

    return unlocked


async def on_task_completed(
    conn: pymysql.Connection, user_id: int, task_id: int
) -> list[dict[str, Any]]:
    task = await task_planner_repo.get_task(conn, user_id, task_id)
    if not task or not int(task.get("is_completed") or 0):
        return []

    unlocked: list[dict[str, Any]] = []
    unlocked.extend(await record_activity_day(conn, user_id))
    unlocked.extend(await evaluate_daily_blueprint(conn, user_id))

    priority = str(task.get("priority_code") or "")
    if priority in ("high", "urgent"):
        created_at = task.get("created_at")
        completed_at = task.get("completed_at")
        if created_at and completed_at:
            if isinstance(created_at, datetime) and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if isinstance(completed_at, datetime) and completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
            elapsed = completed_at - created_at
            if elapsed <= timedelta(hours=2):
                today_key = str(date.today())
                speed_unlocked = await _award(
                    conn,
                    user_id=user_id,
                    delta=POINT_SPEEDRUNNER,
                    reason_code="speedrunner",
                    reference_type="task",
                    reference_id=task_id,
                    cap_key=f"user:{user_id}:speedrunner",
                    season_key=today_key,
                    cap_max=SPEEDRUNNER_DAILY_CAP,
                )
                unlocked.extend(speed_unlocked)
                if speed_unlocked:
                    await gamification_repo.increment_family_counter(
                        conn, user_id=user_id, family="speedrunner"
                    )
                    more = await gamification_repo.check_and_unlock_achievements(conn, user_id)
                    unlocked.extend(more)

    return unlocked


async def on_vote(
    conn: pymysql.Connection,
    *,
    author_user_id: int,
    voter_user_id: int,
    direction: str,
    reference_type: str,
    reference_id: int,
) -> list[dict[str, Any]]:
    if author_user_id == voter_user_id or direction != "up":
        return []
    if reference_type != "blog_post":
        return await _award(
            conn,
            user_id=author_user_id,
            delta=POINT_BLOG_UPVOTE,
            reason_code=f"vote_{direction}",
            reference_type=reference_type,
            reference_id=reference_id,
        )
    return await on_blog_upvote(
        conn,
        author_user_id=author_user_id,
        voter_user_id=voter_user_id,
        post_id=reference_id,
    )


async def on_blog_upvote(
    conn: pymysql.Connection,
    *,
    author_user_id: int,
    voter_user_id: int,
    post_id: int,
) -> list[dict[str, Any]]:
    if author_user_id == voter_user_id:
        return []

    unlocked: list[dict[str, Any]] = []
    post_prefix = f"post:{post_id}"
    total_awarded = await gamification_repo.count_cap_awards(
        conn, reason_code="blog_upvote", reference_key_prefix=post_prefix
    )
    if total_awarded < BLOG_UPVOTE_CAP_PER_POST:
        vote_unlocked = await _award(
            conn,
            user_id=author_user_id,
            delta=POINT_BLOG_UPVOTE,
            reason_code="blog_upvote",
            reference_type="blog_post",
            reference_id=post_id,
            cap_key=f"{post_prefix}:voter:{voter_user_id}",
        )
        unlocked.extend(vote_unlocked)

    upvotes = await gamification_repo.count_blog_upvotes(conn, post_id)
    await gamification_repo.set_family_counter(
        conn, user_id=author_user_id, family="catalyst", counter=upvotes
    )
    catalyst_unlocked = await gamification_repo.check_and_unlock_achievements(
        conn, author_user_id
    )
    unlocked.extend(catalyst_unlocked)

    if upvotes >= 50:
        m50 = await _award(
            conn,
            user_id=author_user_id,
            delta=POINT_BLOG_MILESTONE_50,
            reason_code="blog_upvote_milestone_50",
            reference_type="blog_post",
            reference_id=post_id,
            cap_key=f"{post_prefix}:milestone50",
        )
        unlocked.extend(m50)
    if upvotes >= 100:
        m100 = await _award(
            conn,
            user_id=author_user_id,
            delta=POINT_BLOG_MILESTONE_100,
            reason_code="blog_upvote_milestone_100",
            reference_type="blog_post",
            reference_id=post_id,
            cap_key=f"{post_prefix}:milestone100",
        )
        unlocked.extend(m100)

    return unlocked


async def on_blog_publish(
    conn: pymysql.Connection, author_user_id: int, post_id: int
) -> list[dict[str, Any]]:
    unlocked = await _award(
        conn,
        user_id=author_user_id,
        delta=POINT_BLOG_PUBLISH,
        reason_code="blog_publish",
        reference_type="blog_post",
        reference_id=post_id,
        cap_key=f"post:{post_id}:publish",
    )
    await gamification_repo.increment_family_counter(
        conn, user_id=author_user_id, family="master_author"
    )
    more = await gamification_repo.check_and_unlock_achievements(conn, author_user_id)
    unlocked.extend(more)
    activity = await record_activity_day(conn, author_user_id)
    unlocked.extend(activity)
    return unlocked


async def on_answer_posted(
    conn: pymysql.Connection, author_user_id: int, doubt_id: int
) -> list[dict[str, Any]]:
    unlocked = await _award(
        conn,
        user_id=author_user_id,
        delta=POINT_DOUBT_ANSWER,
        reason_code="doubt_answer",
        reference_type="doubt",
        reference_id=doubt_id,
        cap_key=f"doubt:{doubt_id}:answer:{author_user_id}",
    )
    activity = await record_activity_day(conn, author_user_id)
    unlocked.extend(activity)
    return unlocked


async def on_faculty_endorsed_answer(
    conn: pymysql.Connection,
    *,
    author_user_id: int,
    answer_id: int,
    doubt_id: int,
) -> list[dict[str, Any]]:
    unlocked = await _award(
        conn,
        user_id=author_user_id,
        delta=POINT_FACULTY_ENDORSED,
        reason_code="faculty_endorsed_answer",
        reference_type="doubt_answer",
        reference_id=answer_id,
        cap_key=f"answer:{answer_id}:endorse",
    )
    await gamification_repo.increment_family_counter(
        conn, user_id=author_user_id, family="faculty_favorite"
    )
    more = await gamification_repo.check_and_unlock_achievements(conn, author_user_id)
    unlocked.extend(more)
    activity = await record_activity_day(conn, author_user_id)
    unlocked.extend(activity)
    return unlocked


async def on_moderation_approved(
    conn: pymysql.Connection,
    *,
    reporter_user_id: int,
    report_id: int,
) -> list[dict[str, Any]]:
    unlocked = await _award(
        conn,
        user_id=reporter_user_id,
        delta=POINT_MODERATION,
        reason_code="moderation_approved",
        reference_type="content_report",
        reference_id=report_id,
        cap_key=f"report:{report_id}:moderation",
    )
    await gamification_repo.increment_family_counter(
        conn, user_id=reporter_user_id, family="moderator"
    )
    more = await gamification_repo.check_and_unlock_achievements(conn, reporter_user_id)
    unlocked.extend(more)
    activity = await record_activity_day(conn, reporter_user_id)
    unlocked.extend(activity)
    return unlocked
