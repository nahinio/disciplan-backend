#!/usr/bin/env python3
"""Apply sql/026_achievement_captions.sql idempotently."""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

CAPTIONS: dict[str, str] = {
    "moderator_1": "Have 1 content report you filed approved by moderators",
    "moderator_2": "Have 10 content reports you filed approved by moderators",
    "moderator_3": "Have 25 content reports you filed approved by moderators",
    "moderator_4": "Have 50 content reports you filed approved by moderators",
    "moderator_5": "Have 100 content reports you filed approved by moderators",
    "iron_will_1": "Complete 100% of today's planner tasks for 3 days in a row",
    "iron_will_2": "Complete 100% of today's planner tasks for 7 days in a row",
    "iron_will_3": "Complete 100% of today's planner tasks for 14 days in a row",
    "iron_will_4": "Complete 100% of today's planner tasks for 30 days in a row",
    "iron_will_5": "Complete 100% of today's planner tasks for 90 days in a row",
    "faculty_favorite_1": "Have 1 doubt answer accepted as the official solution by faculty",
    "faculty_favorite_2": "Have 10 doubt answers accepted as official solutions by faculty",
    "faculty_favorite_3": "Have 25 doubt answers accepted as official solutions by faculty",
    "faculty_favorite_4": "Have 50 doubt answers accepted as official solutions by faculty",
    "faculty_favorite_5": "Have 100 doubt answers accepted as official solutions by faculty",
    "master_author_1": "Publish 1 blog post",
    "master_author_2": "Publish 5 blog posts",
    "master_author_3": "Publish 10 blog posts",
    "master_author_4": "Publish 25 blog posts",
    "master_author_5": "Publish 50 blog posts",
    "catalyst_1": "Get 100 upvotes on one of your blog posts",
    "catalyst_2": "Get 250 upvotes on one of your blog posts",
    "catalyst_3": "Get 500 upvotes on one of your blog posts",
    "catalyst_4": "Get 1,000 upvotes on one of your blog posts",
    "catalyst_5": "Get 2,500 upvotes on one of your blog posts",
    "speedrunner_1": "Finish 5 urgent/high-priority tasks within 2 hours of creating them",
    "speedrunner_2": "Finish 15 urgent/high-priority tasks within 2 hours of creating them",
    "speedrunner_3": "Finish 40 urgent/high-priority tasks within 2 hours of creating them",
    "speedrunner_4": "Finish 80 urgent/high-priority tasks within 2 hours of creating them",
    "speedrunner_5": "Finish 150 urgent/high-priority tasks within 2 hours of creating them",
}


def build_ssl() -> ssl.SSLContext | None:
    settings = get_settings()
    if not settings.db_ssl:
        return None
    ca = Path(settings.db_ssl_ca_path)
    if ca.exists():
        ctx = ssl.create_default_context(cafile=str(ca))
    else:
        ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def column_exists(cur: pymysql.cursors.Cursor, table: str, column: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (settings.db_name, table, column),
    )
    return cur.fetchone()[0] > 0


def main() -> None:
    settings = get_settings()
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        ssl=build_ssl(),
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            if not column_exists(cur, "achievement_definitions", "caption"):
                cur.execute(
                    "ALTER TABLE achievement_definitions "
                    "ADD COLUMN caption VARCHAR(255) NULL AFTER label"
                )
                print("Added achievement_definitions.caption")
            else:
                print("achievement_definitions.caption already exists")

            for code, caption in CAPTIONS.items():
                cur.execute(
                    "UPDATE achievement_definitions SET caption = %s WHERE code = %s",
                    (caption, code),
                )

            cur.execute(
                """
                UPDATE badge_types bt
                INNER JOIN achievement_definitions ad ON ad.code = bt.code
                SET bt.description = ad.caption
                WHERE ad.caption IS NOT NULL
                """
            )
            print(f"Updated captions for {len(CAPTIONS)} achievements")

        conn.commit()
        print("Achievement captions migration applied.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
