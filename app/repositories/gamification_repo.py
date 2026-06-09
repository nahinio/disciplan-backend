"""Raw SQL — points, tiers, leaderboard, badges, achievements, streaks."""

from __future__ import annotations

from datetime import date
from typing import Any

import pymysql

from app.db.session import execute, execute_returning_id, fetch_all, fetch_one


async def award_points(
    conn: pymysql.Connection,
    *,
    user_id: int,
    delta: int,
    reason_code: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> None:
    if delta == 0:
        return
    await execute_returning_id(
        conn,
        """
        INSERT INTO point_transactions (user_id, delta_points, reason_code, reference_type, reference_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, delta, reason_code, reference_type, reference_id),
    )
    await execute(
        conn,
        """
        UPDATE user_gamification
        SET total_points = GREATEST(0, total_points + %s)
        WHERE user_id = %s
        """,
        (delta, user_id),
    )
    await _sync_tier(conn, user_id)


async def try_consume_cap(
    conn: pymysql.Connection,
    *,
    reason_code: str,
    reference_key: str,
    season_key: str = "",
    max_awards: int = 1,
) -> bool:
    """Return True if award is allowed (and record cap), False if capped."""
    existing = await fetch_one(
        conn,
        """
        SELECT awarded FROM point_award_caps
        WHERE reason_code = %s AND reference_key = %s AND season_key = %s
        """,
        (reason_code, reference_key, season_key),
    )
    if existing and int(existing["awarded"]) >= max_awards:
        return False
    if existing:
        await execute(
            conn,
            """
            UPDATE point_award_caps SET awarded = awarded + 1
            WHERE reason_code = %s AND reference_key = %s AND season_key = %s
            """,
            (reason_code, reference_key, season_key),
        )
        return int(existing["awarded"]) + 1 <= max_awards
    try:
        await execute_returning_id(
            conn,
            """
            INSERT INTO point_award_caps (reason_code, reference_key, season_key, awarded)
            VALUES (%s, %s, %s, 1)
            """,
            (reason_code, reference_key, season_key),
        )
        return True
    except Exception:
        return False


async def count_cap_awards(
    conn: pymysql.Connection,
    *,
    reason_code: str,
    reference_key_prefix: str,
) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COALESCE(SUM(awarded), 0) AS n
        FROM point_award_caps
        WHERE reason_code = %s AND reference_key LIKE %s
        """,
        (reason_code, f"{reference_key_prefix}%"),
    )
    return int(row["n"]) if row else 0


async def _sync_tier(conn: pymysql.Connection, user_id: int) -> None:
    row = await fetch_one(
        conn, "SELECT total_points FROM user_gamification WHERE user_id = %s", (user_id,)
    )
    if not row:
        return
    tier = await fetch_one(
        conn,
        """
        SELECT id FROM gamification_tiers
        WHERE min_points <= %s
        ORDER BY min_points DESC
        LIMIT 1
        """,
        (row["total_points"],),
    )
    if tier:
        await execute(
            conn,
            "UPDATE user_gamification SET tier_id = %s WHERE user_id = %s",
            (tier["id"], user_id),
        )


async def get_tier_info(conn: pymysql.Connection, user_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT
            ug.total_points,
            gt.code AS tier_code,
            gt.label AS tier_label,
            gt.min_points AS tier_min_points,
            ngt.min_points AS next_tier_points,
            ngt.label AS next_tier_label
        FROM user_gamification ug
        INNER JOIN gamification_tiers gt ON gt.id = ug.tier_id
        LEFT JOIN gamification_tiers ngt ON ngt.id = gt.next_tier_id
        WHERE ug.user_id = %s
        """,
        (user_id,),
    )


async def increment_family_counter(
    conn: pymysql.Connection,
    *,
    user_id: int,
    family: str,
    delta: int = 1,
) -> int:
    await execute(
        conn,
        """
        INSERT INTO user_achievement_progress (user_id, family, counter, unlocked_level)
        VALUES (%s, %s, %s, 0)
        ON DUPLICATE KEY UPDATE counter = counter + %s
        """,
        (user_id, family, delta, delta),
    )
    row = await fetch_one(
        conn,
        "SELECT counter FROM user_achievement_progress WHERE user_id = %s AND family = %s",
        (user_id, family),
    )
    return int(row["counter"]) if row else 0


async def set_family_counter(
    conn: pymysql.Connection,
    *,
    user_id: int,
    family: str,
    counter: int,
) -> None:
    await execute(
        conn,
        """
        INSERT INTO user_achievement_progress (user_id, family, counter, unlocked_level)
        VALUES (%s, %s, %s, 0)
        ON DUPLICATE KEY UPDATE counter = %s
        """,
        (user_id, family, counter, counter),
    )


async def check_and_unlock_achievements(
    conn: pymysql.Connection, user_id: int
) -> list[dict[str, Any]]:
    """Unlock badges whose thresholds are met; return newly unlocked achievements."""
    rows = await fetch_all(
        conn,
        """
        SELECT ad.code, ad.family, ad.level, ad.label, ad.threshold, ad.icon_key,
               COALESCE(uap.counter, 0) AS counter,
               COALESCE(uap.unlocked_level, 0) AS unlocked_level
        FROM achievement_definitions ad
        LEFT JOIN user_achievement_progress uap
            ON uap.family = ad.family AND uap.user_id = %s
        ORDER BY ad.family, ad.level
        """,
        (user_id,),
    )

    newly_unlocked: list[dict[str, Any]] = []
    family_levels: dict[str, int] = {}

    for row in rows:
        family = row["family"]
        level = int(row["level"])
        counter = int(row["counter"])
        threshold = int(row["threshold"])
        unlocked = family_levels.get(family, int(row["unlocked_level"]))

        if counter >= threshold and level > unlocked:
            family_levels[family] = level
            await award_badge(
                conn,
                user_id=user_id,
                badge_code=row["code"],
                awarded_by_user_id=None,
                reference_type="achievement",
                reference_id=None,
            )
            newly_unlocked.append(
                {
                    "code": row["code"],
                    "label": row["label"],
                    "family": family,
                    "level": level,
                    "icon_url": f"/badges/demo/{row['icon_key']}.svg",
                }
            )

    for family, level in family_levels.items():
        await execute(
            conn,
            """
            INSERT INTO user_achievement_progress (user_id, family, counter, unlocked_level)
            VALUES (%s, %s, 0, %s)
            ON DUPLICATE KEY UPDATE unlocked_level = GREATEST(unlocked_level, %s)
            """,
            (user_id, family, level, level),
        )

    return newly_unlocked


async def get_streak(
    conn: pymysql.Connection, user_id: int, streak_code: str
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """
        SELECT current_count, best_count, last_date
        FROM user_streaks
        WHERE user_id = %s AND streak_code = %s
        """,
        (user_id, streak_code),
    )


async def update_streak(
    conn: pymysql.Connection,
    *,
    user_id: int,
    streak_code: str,
    activity_date: date,
    reset_on_gap: bool = True,
) -> dict[str, int]:
    row = await get_streak(conn, user_id, streak_code)
    if not row:
        await execute(
            conn,
            """
            INSERT INTO user_streaks (user_id, streak_code, current_count, best_count, last_date)
            VALUES (%s, %s, 1, 1, %s)
            """,
            (user_id, streak_code, activity_date),
        )
        return {"current_count": 1, "best_count": 1}

    last = row["last_date"]
    current = int(row["current_count"])
    best = int(row["best_count"])

    if last == activity_date:
        return {"current_count": current, "best_count": best}

    if last is not None:
        gap = (activity_date - last).days
        if gap == 1:
            current += 1
        elif reset_on_gap and gap > 1:
            current = 1
        elif not reset_on_gap:
            current += 1
    else:
        current = 1

    best = max(best, current)
    await execute(
        conn,
        """
        UPDATE user_streaks
        SET current_count = %s, best_count = %s, last_date = %s
        WHERE user_id = %s AND streak_code = %s
        """,
        (current, best, activity_date, user_id, streak_code),
    )
    return {"current_count": current, "best_count": best}


async def list_user_streaks(conn: pymysql.Connection, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT streak_code, current_count, best_count, last_date
        FROM user_streaks
        WHERE user_id = %s
        ORDER BY streak_code
        """,
        (user_id,),
    )


async def count_blog_upvotes(conn: pymysql.Connection, post_id: int) -> int:
    row = await fetch_one(
        conn,
        """
        SELECT COUNT(*) AS n
        FROM blog_post_votes bpv
        INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
        WHERE bpv.post_id = %s AND vd.code = 'up'
        """,
        (post_id,),
    )
    return int(row["n"]) if row else 0


async def get_gamification_me(conn: pymysql.Connection, user_id: int) -> dict[str, Any]:
    tier = await get_tier_info(conn, user_id) or {}
    streaks = await list_user_streaks(conn, user_id)
    badges = await list_user_badges(conn, user_id)
    return {
        "total_points": int(tier.get("total_points") or 0),
        "tier_code": tier.get("tier_code"),
        "tier_label": tier.get("tier_label"),
        "next_tier_points": int(tier["next_tier_points"]) if tier.get("next_tier_points") else None,
        "next_tier_label": tier.get("next_tier_label"),
        "streaks": streaks,
        "badges": badges,
    }


async def list_achievement_ladder(
    conn: pymysql.Connection, user_id: int
) -> list[dict[str, Any]]:
    rows = await fetch_all(
        conn,
        """
        SELECT
            ad.code, ad.family, ad.level, ad.label, ad.caption, ad.threshold, ad.icon_key,
            COALESCE(uap.counter, 0) AS counter,
            COALESCE(uap.unlocked_level, 0) AS unlocked_level,
            ub.id IS NOT NULL AS is_unlocked
        FROM achievement_definitions ad
        LEFT JOIN user_achievement_progress uap
            ON uap.family = ad.family AND uap.user_id = %s
        LEFT JOIN badge_types bt ON bt.code = ad.code
        LEFT JOIN user_badges ub ON ub.badge_type_id = bt.id AND ub.user_id = %s
        ORDER BY ad.family, ad.level
        """,
        (user_id, user_id),
    )
    return [
        {
            **row,
            "icon_url": f"/badges/demo/{row['icon_key']}.svg",
            "is_unlocked": bool(row["is_unlocked"]) or int(row["level"]) <= int(row["unlocked_level"]),
        }
        for row in rows
    ]


async def get_leaderboard(
    conn: pymysql.Connection, *, period: str = "all_time", limit: int = 50
) -> list[dict[str, Any]]:
    if period == "today":
        return await fetch_all(
            conn,
            """
            SELECT lb.user_id, lb.display_name, lb.today_points AS points,
                   gt.label AS tier_label, gt.code AS tier_code,
                   lb.rank_position AS leaderboard_rank
            FROM v_leaderboard_today lb
            INNER JOIN user_gamification ug ON ug.user_id = lb.user_id
            INNER JOIN gamification_tiers gt ON gt.id = ug.tier_id
            INNER JOIN users u ON u.id = lb.user_id
            INNER JOIN roles r ON r.id = u.role_id AND r.code = 'student'
            INNER JOIN user_statuses us ON us.id = u.status_id AND us.code = 'active'
            ORDER BY lb.rank_position
            LIMIT %s
            """,
            (limit,),
        )
    return await fetch_all(
        conn,
        """
        SELECT ranked.user_id, ranked.display_name, ranked.points,
               ranked.tier_label, ranked.tier_code, ranked.leaderboard_rank
        FROM (
            SELECT ug.user_id, up.display_name, ug.total_points AS points,
                   gt.label AS tier_label, gt.code AS tier_code,
                   RANK() OVER (ORDER BY ug.total_points DESC) AS leaderboard_rank
            FROM user_gamification ug
            INNER JOIN user_profiles up ON up.user_id = ug.user_id
            INNER JOIN gamification_tiers gt ON gt.id = ug.tier_id
            INNER JOIN users u ON u.id = ug.user_id
            INNER JOIN roles r ON r.id = u.role_id AND r.code = 'student'
            INNER JOIN user_statuses us ON us.id = u.status_id AND us.code = 'active'
        ) ranked
        ORDER BY ranked.leaderboard_rank
        LIMIT %s
        """,
        (limit,),
    )


async def get_user_rank(
    conn: pymysql.Connection, user_id: int, *, period: str = "all_time"
) -> dict[str, Any] | None:
    if period == "today":
        return await fetch_one(
            conn,
            """
            SELECT lb.user_id, lb.display_name, lb.today_points AS points,
                   gt.label AS tier_label, gt.code AS tier_code,
                   lb.rank_position AS leaderboard_rank
            FROM v_leaderboard_today lb
            INNER JOIN user_gamification ug ON ug.user_id = lb.user_id
            INNER JOIN gamification_tiers gt ON gt.id = ug.tier_id
            INNER JOIN users u ON u.id = lb.user_id
            INNER JOIN roles r ON r.id = u.role_id AND r.code = 'student'
            WHERE lb.user_id = %s
            """,
            (user_id,),
        )
    return await fetch_one(
        conn,
        """
        SELECT ranked.user_id, ranked.display_name, ranked.points,
               ranked.tier_label, ranked.tier_code, ranked.leaderboard_rank
        FROM (
            SELECT ug.user_id, up.display_name, ug.total_points AS points,
                   gt.label AS tier_label, gt.code AS tier_code,
                   RANK() OVER (ORDER BY ug.total_points DESC) AS leaderboard_rank
            FROM user_gamification ug
            INNER JOIN user_profiles up ON up.user_id = ug.user_id
            INNER JOIN gamification_tiers gt ON gt.id = ug.tier_id
            INNER JOIN users u ON u.id = ug.user_id
            INNER JOIN roles r ON r.id = u.role_id AND r.code = 'student'
            INNER JOIN user_statuses us ON us.id = u.status_id AND us.code = 'active'
        ) ranked
        WHERE ranked.user_id = %s
        """,
        (user_id,),
    )


async def list_point_history(
    conn: pymysql.Connection, user_id: int, *, limit: int = 30
) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT id, delta_points, reason_code, reference_type, reference_id, created_at
        FROM point_transactions
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )


async def admin_adjust_points(
    conn: pymysql.Connection,
    *,
    user_id: int,
    delta: int,
    reason_code: str = "admin_adjustment",
) -> None:
    await award_points(conn, user_id=user_id, delta=delta, reason_code=reason_code)


async def list_user_badges(conn: pymysql.Connection, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        conn,
        """
        SELECT ub.id, bt.code, bt.label, bt.description, bt.family, bt.level, bt.icon_key,
               ub.awarded_at,
               up.display_name AS awarded_by_name
        FROM user_badges ub
        INNER JOIN badge_types bt ON bt.id = ub.badge_type_id
        LEFT JOIN user_profiles up ON up.user_id = ub.awarded_by_user_id
        WHERE ub.user_id = %s
        ORDER BY ub.awarded_at DESC
        """,
        (user_id,),
    )


async def award_badge(
    conn: pymysql.Connection,
    *,
    user_id: int,
    badge_code: str,
    awarded_by_user_id: int | None,
    reference_type: str | None = None,
    reference_id: int | None = None,
) -> int:
    badge = await fetch_one(
        conn, "SELECT id FROM badge_types WHERE code = %s", (badge_code,)
    )
    if not badge:
        raise ValueError(f"Unknown badge: {badge_code}")
    return await execute_returning_id(
        conn,
        """
        INSERT INTO user_badges (user_id, badge_type_id, awarded_by_user_id, reference_type, reference_id)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            awarded_by_user_id = VALUES(awarded_by_user_id),
            reference_type = VALUES(reference_type),
            reference_id = VALUES(reference_id),
            awarded_at = UTC_TIMESTAMP(3)
        """,
        (user_id, badge["id"], awarded_by_user_id, reference_type, reference_id),
    )
