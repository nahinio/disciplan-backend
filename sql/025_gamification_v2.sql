-- Gamification v2: 10 tiers, achievements, streaks, award caps

SET FOREIGN_KEY_CHECKS = 0;

UPDATE user_gamification SET tier_id = 1;
DELETE FROM gamification_tiers;

INSERT INTO gamification_tiers (id, code, label, min_points, next_tier_id) VALUES
    (1,  'recruit',     'Recruit',     0,    2),
    (2,  'rookie',      'Rookie',      50,   3),
    (3,  'contender',   'Contender',   150,  4),
    (4,  'specialist',  'Specialist',  300,  5),
    (5,  'elite',       'Elite',       500,  6),
    (6,  'veteran',     'Veteran',     750,  7),
    (7,  'master',      'Master',      1050, 8),
    (8,  'champion',    'Champion',    1400, 9),
    (9,  'legend',      'Legend',      1800, 10),
    (10, 'titan',       'Titan',       2300, NULL);

UPDATE user_gamification ug
SET tier_id = COALESCE(
    (
        SELECT gt.id FROM gamification_tiers gt
        WHERE gt.min_points <= ug.total_points
        ORDER BY gt.min_points DESC
        LIMIT 1
    ),
    1
);

SET FOREIGN_KEY_CHECKS = 1;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_achievement_progress (
    user_id         BIGINT UNSIGNED  NOT NULL,
    family          VARCHAR(40)      NOT NULL,
    counter         INT UNSIGNED     NOT NULL DEFAULT 0,
    unlocked_level  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, family),
    CONSTRAINT fk_user_achievement_progress_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_streaks (
    user_id         BIGINT UNSIGNED NOT NULL,
    streak_code     VARCHAR(40)     NOT NULL,
    current_count   SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    best_count      SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    last_date       DATE            NULL,
    updated_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, streak_code),
    CONSTRAINT fk_user_streaks_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS point_award_caps (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    reason_code     VARCHAR(40)     NOT NULL,
    reference_key   VARCHAR(120)    NOT NULL,
    season_key      VARCHAR(40)     NOT NULL DEFAULT '',
    awarded         INT UNSIGNED    NOT NULL DEFAULT 1,
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_point_award_caps (reason_code, reference_key, season_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE badge_types
    ADD COLUMN family VARCHAR(40) NULL,
    ADD COLUMN level TINYINT UNSIGNED NULL,
    ADD COLUMN icon_key VARCHAR(80) NULL;

-- Achievement definitions (6 families x 5 levels)
INSERT IGNORE INTO achievement_definitions (code, family, level, label, threshold, icon_key) VALUES
    ('moderator_1', 'moderator', 1, 'Moderator I', 1, 'moderator'),
    ('moderator_2', 'moderator', 2, 'Moderator II', 10, 'moderator'),
    ('moderator_3', 'moderator', 3, 'Moderator III', 25, 'moderator'),
    ('moderator_4', 'moderator', 4, 'Moderator IV', 50, 'moderator'),
    ('moderator_5', 'moderator', 5, 'Moderator V', 100, 'moderator'),
    ('iron_will_1', 'iron_will', 1, 'Iron Will I', 3, 'iron_will'),
    ('iron_will_2', 'iron_will', 2, 'Iron Will II', 7, 'iron_will'),
    ('iron_will_3', 'iron_will', 3, 'Iron Will III', 14, 'iron_will'),
    ('iron_will_4', 'iron_will', 4, 'Iron Will IV', 30, 'iron_will'),
    ('iron_will_5', 'iron_will', 5, 'Iron Will V', 90, 'iron_will'),
    ('faculty_favorite_1', 'faculty_favorite', 1, 'Faculty Favorite I', 1, 'faculty_favorite'),
    ('faculty_favorite_2', 'faculty_favorite', 2, 'Faculty Favorite II', 10, 'faculty_favorite'),
    ('faculty_favorite_3', 'faculty_favorite', 3, 'Faculty Favorite III', 25, 'faculty_favorite'),
    ('faculty_favorite_4', 'faculty_favorite', 4, 'Faculty Favorite IV', 50, 'faculty_favorite'),
    ('faculty_favorite_5', 'faculty_favorite', 5, 'Faculty Favorite V', 100, 'faculty_favorite'),
    ('master_author_1', 'master_author', 1, 'Master Author I', 1, 'master_author'),
    ('master_author_2', 'master_author', 2, 'Master Author II', 5, 'master_author'),
    ('master_author_3', 'master_author', 3, 'Master Author III', 10, 'master_author'),
    ('master_author_4', 'master_author', 4, 'Master Author IV', 25, 'master_author'),
    ('master_author_5', 'master_author', 5, 'Master Author V', 50, 'master_author'),
    ('catalyst_1', 'catalyst', 1, 'Catalyst I', 100, 'catalyst'),
    ('catalyst_2', 'catalyst', 2, 'Catalyst II', 250, 'catalyst'),
    ('catalyst_3', 'catalyst', 3, 'Catalyst III', 500, 'catalyst'),
    ('catalyst_4', 'catalyst', 4, 'Catalyst IV', 1000, 'catalyst'),
    ('catalyst_5', 'catalyst', 5, 'Catalyst V', 2500, 'catalyst'),
    ('speedrunner_1', 'speedrunner', 1, 'Speedrunner I', 5, 'speedrunner'),
    ('speedrunner_2', 'speedrunner', 2, 'Speedrunner II', 15, 'speedrunner'),
    ('speedrunner_3', 'speedrunner', 3, 'Speedrunner III', 40, 'speedrunner'),
    ('speedrunner_4', 'speedrunner', 4, 'Speedrunner IV', 80, 'speedrunner'),
    ('speedrunner_5', 'speedrunner', 5, 'Speedrunner V', 150, 'speedrunner');

INSERT IGNORE INTO badge_types (code, label, description, family, level, icon_key) VALUES
    ('moderator_1', 'Moderator I', 'Approved moderation reports', 'moderator', 1, 'moderator'),
    ('moderator_2', 'Moderator II', 'Approved moderation reports', 'moderator', 2, 'moderator'),
    ('moderator_3', 'Moderator III', 'Approved moderation reports', 'moderator', 3, 'moderator'),
    ('moderator_4', 'Moderator IV', 'Approved moderation reports', 'moderator', 4, 'moderator'),
    ('moderator_5', 'Moderator V', 'Approved moderation reports', 'moderator', 5, 'moderator'),
    ('iron_will_1', 'Iron Will I', 'Consecutive full blueprint days', 'iron_will', 1, 'iron_will'),
    ('iron_will_2', 'Iron Will II', 'Consecutive full blueprint days', 'iron_will', 2, 'iron_will'),
    ('iron_will_3', 'Iron Will III', 'Consecutive full blueprint days', 'iron_will', 3, 'iron_will'),
    ('iron_will_4', 'Iron Will IV', 'Consecutive full blueprint days', 'iron_will', 4, 'iron_will'),
    ('iron_will_5', 'Iron Will V', 'Consecutive full blueprint days', 'iron_will', 5, 'iron_will'),
    ('faculty_favorite_1', 'Faculty Favorite I', 'Faculty-endorsed doubt solutions', 'faculty_favorite', 1, 'faculty_favorite'),
    ('faculty_favorite_2', 'Faculty Favorite II', 'Faculty-endorsed doubt solutions', 'faculty_favorite', 2, 'faculty_favorite'),
    ('faculty_favorite_3', 'Faculty Favorite III', 'Faculty-endorsed doubt solutions', 'faculty_favorite', 3, 'faculty_favorite'),
    ('faculty_favorite_4', 'Faculty Favorite IV', 'Faculty-endorsed doubt solutions', 'faculty_favorite', 4, 'faculty_favorite'),
    ('faculty_favorite_5', 'Faculty Favorite V', 'Faculty-endorsed doubt solutions', 'faculty_favorite', 5, 'faculty_favorite'),
    ('master_author_1', 'Master Author I', 'Published blog posts', 'master_author', 1, 'master_author'),
    ('master_author_2', 'Master Author II', 'Published blog posts', 'master_author', 2, 'master_author'),
    ('master_author_3', 'Master Author III', 'Published blog posts', 'master_author', 3, 'master_author'),
    ('master_author_4', 'Master Author IV', 'Published blog posts', 'master_author', 4, 'master_author'),
    ('master_author_5', 'Master Author V', 'Published blog posts', 'master_author', 5, 'master_author'),
    ('catalyst_1', 'Catalyst I', 'Blog upvotes received', 'catalyst', 1, 'catalyst'),
    ('catalyst_2', 'Catalyst II', 'Blog upvotes received', 'catalyst', 2, 'catalyst'),
    ('catalyst_3', 'Catalyst III', 'Blog upvotes received', 'catalyst', 3, 'catalyst'),
    ('catalyst_4', 'Catalyst IV', 'Blog upvotes received', 'catalyst', 4, 'catalyst'),
    ('catalyst_5', 'Catalyst V', 'Blog upvotes received', 'catalyst', 5, 'catalyst'),
    ('speedrunner_1', 'Speedrunner I', 'Rapid high-priority task completions', 'speedrunner', 1, 'speedrunner'),
    ('speedrunner_2', 'Speedrunner II', 'Rapid high-priority task completions', 'speedrunner', 2, 'speedrunner'),
    ('speedrunner_3', 'Speedrunner III', 'Rapid high-priority task completions', 'speedrunner', 3, 'speedrunner'),
    ('speedrunner_4', 'Speedrunner IV', 'Rapid high-priority task completions', 'speedrunner', 4, 'speedrunner'),
    ('speedrunner_5', 'Speedrunner V', 'Rapid high-priority task completions', 'speedrunner', 5, 'speedrunner');
