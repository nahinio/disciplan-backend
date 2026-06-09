"""Public student profile: heatmap, courses, blogs, gamification summary."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pymysql

from app.db.session import fetch_all, fetch_one
from app.repositories import academic_repo, blog_repo, gamification_repo


async def get_public_student_profile(
    conn: pymysql.Connection, user_id: int
) -> dict[str, Any] | None:
    row = await fetch_one(
        conn,
        """
        SELECT
            u.id, up.display_name, up.bio,
            af.secure_url AS avatar_url,
            d.code AS department_code, d.name AS department_name,
            r.code AS role_code,
            us.code AS status_code,
            ug.total_points,
            gt.code AS tier_code,
            gt.label AS tier_label
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        INNER JOIN user_statuses us ON us.id = u.status_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN files af ON af.id = up.avatar_file_id AND af.deleted_at IS NULL
        LEFT JOIN departments d ON d.id = up.department_id
        LEFT JOIN user_gamification ug ON ug.user_id = u.id
        LEFT JOIN gamification_tiers gt ON gt.id = ug.tier_id
        WHERE u.id = %s
        """,
        (user_id,),
    )
    if not row or row["role_code"] != "student" or row["status_code"] != "active":
        return None

    tier_info = await gamification_repo.get_tier_info(conn, user_id)
    badges = await gamification_repo.list_user_badges(conn, user_id)
    streaks = await gamification_repo.list_user_streaks(conn, user_id)
    rank = await gamification_repo.get_user_rank(conn, user_id, period="all_time")
    courses = await academic_repo.list_user_sections(conn, user_id, "student")
    raw_blogs = await blog_repo.list_posts_by_author(conn, user_id, limit=12)
    blogs = [_serialize_blog_row(b) for b in raw_blogs]
    heatmap = await get_task_completion_heatmap(conn, user_id)

    unlocked_badges = [
        {
            "code": b["code"],
            "label": b["label"],
            "family": b.get("family"),
            "level": b.get("level"),
            "icon_url": f"/badges/demo/{b['icon_key']}.svg" if b.get("icon_key") else None,
            "caption": b.get("description"),
            "awarded_at": _iso_dt(b.get("awarded_at")),
        }
        for b in badges
    ]

    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "bio": row.get("bio"),
        "avatar_url": row.get("avatar_url"),
        "department_code": row.get("department_code"),
        "department_name": row.get("department_name"),
        "total_points": int(row.get("total_points") or 0),
        "tier_code": row.get("tier_code"),
        "tier_label": row.get("tier_label"),
        "next_tier_points": tier_info.get("next_tier_points") if tier_info else None,
        "next_tier_label": tier_info.get("next_tier_label") if tier_info else None,
        "rank": rank.get("leaderboard_rank") if rank else None,
        "streaks": streaks,
        "badges": unlocked_badges,
        "courses": courses,
        "blogs": blogs,
        "heatmap": heatmap,
    }


def _iso_dt(value: datetime | date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _serialize_blog_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "published_at": _iso_dt(row.get("published_at")),
        "created_at": _iso_dt(row.get("created_at")),
        "upvotes": int(row.get("upvotes") or 0),
    }


async def get_task_completion_heatmap(
    conn: pymysql.Connection,
    user_id: int,
    *,
    weeks: int = 52,
) -> dict[str, Any]:
    end = date.today()
    start = end - timedelta(days=weeks * 7 - 1)

    rows = await fetch_all(
        conn,
        """
        SELECT
            DATE(COALESCE(ut.completed_at, ut.scheduled_for_date, ut.created_at)) AS activity_date,
            COUNT(*) AS task_count
        FROM user_tasks ut
        WHERE ut.user_id = %s
          AND ut.is_completed = 1
          AND DATE(COALESCE(ut.completed_at, ut.scheduled_for_date, ut.created_at)) >= %s
          AND DATE(COALESCE(ut.completed_at, ut.scheduled_for_date, ut.created_at)) <= %s
        GROUP BY activity_date
        ORDER BY activity_date
        """,
        (user_id, start, end),
    )

    by_date = {str(r["activity_date"]): int(r["task_count"]) for r in rows}
    days: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        days.append({"date": key, "count": by_date.get(key, 0)})
        cursor += timedelta(days=1)

    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    max_count = max((d["count"] for d in days), default=0)

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": days,
        "total_completions": total,
        "active_days": active_days,
        "max_count": max_count,
    }
