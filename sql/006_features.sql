-- Feature tables: task types, badges, threaded doubt answers

ALTER TABLE user_tasks
    ADD COLUMN assessment_type_id TINYINT UNSIGNED NULL AFTER course_id,
    ADD CONSTRAINT fk_user_tasks_assessment_type
        FOREIGN KEY (assessment_type_id) REFERENCES assessment_types (id) ON DELETE SET NULL;

ALTER TABLE section_doubt_answers
    ADD COLUMN parent_answer_id BIGINT UNSIGNED NULL AFTER doubt_id,
    ADD CONSTRAINT fk_doubt_answers_parent
        FOREIGN KEY (parent_answer_id) REFERENCES section_doubt_answers (id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS badge_types (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(40)      NOT NULL,
    label       VARCHAR(80)      NOT NULL,
    description VARCHAR(255)     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_badge_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_badges (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    user_id             BIGINT UNSIGNED  NOT NULL,
    badge_type_id       TINYINT UNSIGNED NOT NULL,
    awarded_by_user_id  BIGINT UNSIGNED  NULL,
    reference_type      VARCHAR(40)      NULL,
    reference_id        BIGINT UNSIGNED  NULL,
    awarded_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_badges_user_badge (user_id, badge_type_id),
    CONSTRAINT fk_user_badges_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_badges_type
        FOREIGN KEY (badge_type_id) REFERENCES badge_types (id),
    CONSTRAINT fk_user_badges_awarder
        FOREIGN KEY (awarded_by_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO badge_types (code, label, description) VALUES
    ('helpful_peer',    'Helpful Peer',    'Awarded for highly upvoted forum or doubt answers'),
    ('top_contributor', 'Top Contributor', 'Awarded for exceptional blog contributions'),
    ('verified_expert', 'Verified Expert', 'Faculty-verified academic excellence');
