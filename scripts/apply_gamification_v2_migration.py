#!/usr/bin/env python3
"""Apply sql/025_gamification_v2.sql idempotently."""

from __future__ import annotations

import ssl
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

ACHIEVEMENTS = [
    ("moderator_1", "moderator", 1, "Moderator I", 1, "moderator"),
    ("moderator_2", "moderator", 2, "Moderator II", 10, "moderator"),
    ("moderator_3", "moderator", 3, "Moderator III", 25, "moderator"),
    ("moderator_4", "moderator", 4, "Moderator IV", 50, "moderator"),
    ("moderator_5", "moderator", 5, "Moderator V", 100, "moderator"),
    ("iron_will_1", "iron_will", 1, "Iron Will I", 3, "iron_will"),
    ("iron_will_2", "iron_will", 2, "Iron Will II", 7, "iron_will"),
    ("iron_will_3", "iron_will", 3, "Iron Will III", 14, "iron_will"),
    ("iron_will_4", "iron_will", 4, "Iron Will IV", 30, "iron_will"),
    ("iron_will_5", "iron_will", 5, "Iron Will V", 90, "iron_will"),
    ("faculty_favorite_1", "faculty_favorite", 1, "Faculty Favorite I", 1, "faculty_favorite"),
    ("faculty_favorite_2", "faculty_favorite", 2, "Faculty Favorite II", 10, "faculty_favorite"),
    ("faculty_favorite_3", "faculty_favorite", 3, "Faculty Favorite III", 25, "faculty_favorite"),
    ("faculty_favorite_4", "faculty_favorite", 4, "Faculty Favorite IV", 50, "faculty_favorite"),
    ("faculty_favorite_5", "faculty_favorite", 5, "Faculty Favorite V", 100, "faculty_favorite"),
    ("master_author_1", "master_author", 1, "Master Author I", 1, "master_author"),
    ("master_author_2", "master_author", 2, "Master Author II", 5, "master_author"),
    ("master_author_3", "master_author", 3, "Master Author III", 10, "master_author"),
    ("master_author_4", "master_author", 4, "Master Author IV", 25, "master_author"),
    ("master_author_5", "master_author", 5, "Master Author V", 50, "master_author"),
    ("catalyst_1", "catalyst", 1, "Catalyst I", 100, "catalyst"),
    ("catalyst_2", "catalyst", 2, "Catalyst II", 250, "catalyst"),
    ("catalyst_3", "catalyst", 3, "Catalyst III", 500, "catalyst"),
    ("catalyst_4", "catalyst", 4, "Catalyst IV", 1000, "catalyst"),
    ("catalyst_5", "catalyst", 5, "Catalyst V", 2500, "catalyst"),
    ("speedrunner_1", "speedrunner", 1, "Speedrunner I", 5, "speedrunner"),
    ("speedrunner_2", "speedrunner", 2, "Speedrunner II", 15, "speedrunner"),
    ("speedrunner_3", "speedrunner", 3, "Speedrunner III", 40, "speedrunner"),
    ("speedrunner_4", "speedrunner", 4, "Speedrunner IV", 80, "speedrunner"),
    ("speedrunner_5", "speedrunner", 5, "Speedrunner V", 150, "speedrunner"),
]

TIERS = [
    (1, "recruit", "Recruit", 0, 2),
    (2, "rookie", "Rookie", 50, 3),
    (3, "contender", "Contender", 150, 4),
    (4, "specialist", "Specialist", 300, 5),
    (5, "elite", "Elite", 500, 6),
    (6, "veteran", "Veteran", 750, 7),
    (7, "master", "Master", 1050, 8),
    (8, "champion", "Champion", 1400, 9),
    (9, "legend", "Legend", 1800, 10),
    (10, "titan", "Titan", 2300, None),
]


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


def table_exists(cur: pymysql.cursors.Cursor, table: str) -> bool:
    settings = get_settings()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (settings.db_name, table),
    )
    return cur.fetchone()[0] > 0


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


def tier_v2_applied(cur: pymysql.cursors.Cursor) -> bool:
    cur.execute("SELECT COUNT(*) FROM gamification_tiers WHERE code = 'titan'")
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS achievement_definitions (
                    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    code        VARCHAR(60)       NOT NULL,
                    family      VARCHAR(40)       NOT NULL,
                    level       TINYINT UNSIGNED  NOT NULL,
                    label       VARCHAR(80)       NOT NULL,
                    threshold   INT UNSIGNED      NOT NULL,
                    icon_key    VARCHAR(80)       NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_achievement_definitions_code (code),
                    KEY idx_achievement_definitions_family_level (family, level)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_achievement_progress (
                    user_id         BIGINT UNSIGNED  NOT NULL,
                    family          VARCHAR(40)      NOT NULL,
                    counter         INT UNSIGNED     NOT NULL DEFAULT 0,
                    unlocked_level  TINYINT UNSIGNED NOT NULL DEFAULT 0,
                    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                        ON UPDATE CURRENT_TIMESTAMP(3),
                    PRIMARY KEY (user_id, family),
                    CONSTRAINT fk_user_achievement_progress_user
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_streaks (
                    user_id         BIGINT UNSIGNED NOT NULL,
                    streak_code     VARCHAR(40)     NOT NULL,
                    current_count   SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                    best_count      SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                    last_date       DATE            NULL,
                    updated_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                        ON UPDATE CURRENT_TIMESTAMP(3),
                    PRIMARY KEY (user_id, streak_code),
                    CONSTRAINT fk_user_streaks_user
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS point_award_caps (
                    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    reason_code     VARCHAR(40)     NOT NULL,
                    reference_key   VARCHAR(120)    NOT NULL,
                    season_key      VARCHAR(40)     NOT NULL DEFAULT '',
                    awarded         INT UNSIGNED    NOT NULL DEFAULT 1,
                    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_point_award_caps (reason_code, reference_key, season_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            print("Ensured gamification v2 tables exist")

            for col in ("family", "level", "icon_key"):
                if not column_exists(cur, "badge_types", col):
                    if col == "level":
                        cur.execute(
                            f"ALTER TABLE badge_types ADD COLUMN {col} TINYINT UNSIGNED NULL"
                        )
                    else:
                        cur.execute(
                            f"ALTER TABLE badge_types ADD COLUMN {col} VARCHAR(80) NULL"
                        )
                    print(f"Added badge_types.{col}")

            if not tier_v2_applied(cur):
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for tid, code, label, min_pts, _next_id in TIERS:
                    cur.execute(
                        """
                        INSERT INTO gamification_tiers (id, code, label, min_points, next_tier_id)
                        VALUES (%s, %s, %s, %s, NULL)
                        ON DUPLICATE KEY UPDATE
                            code = VALUES(code),
                            label = VALUES(label),
                            min_points = VALUES(min_points),
                            next_tier_id = NULL
                        """,
                        (tid, code, label, min_pts),
                    )
                for tid, _code, _label, _min_pts, next_id in TIERS:
                    if next_id is not None:
                        cur.execute(
                            "UPDATE gamification_tiers SET next_tier_id = %s WHERE id = %s",
                            (next_id, tid),
                        )
                cur.execute("DELETE FROM gamification_tiers WHERE id > 10")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                cur.execute(
                    """
                    UPDATE user_gamification ug
                    SET tier_id = COALESCE(
                        (
                            SELECT gt.id FROM gamification_tiers gt
                            WHERE gt.min_points <= ug.total_points
                            ORDER BY gt.min_points DESC
                            LIMIT 1
                        ),
                        1
                    )
                    """
                )
                print("Replaced gamification tiers with v2 (10 tiers)")
            else:
                print("Gamification tiers v2 already applied")

            for row in ACHIEVEMENTS:
                cur.execute(
                    """
                    INSERT IGNORE INTO achievement_definitions
                        (code, family, level, label, threshold, icon_key)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    row,
                )
                code, family, level, label, _threshold, icon_key = row
                cur.execute(
                    """
                    INSERT IGNORE INTO badge_types (code, label, description, family, level, icon_key)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (code, label, label, family, level, icon_key),
                )

        conn.commit()
        print("025_gamification_v2 migration applied.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
