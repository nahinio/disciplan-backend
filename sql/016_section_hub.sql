-- Section hub: resources, grade rubric, announcement comments, practice scope, teams/chat

CREATE TABLE IF NOT EXISTS section_resources (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NOT NULL,
    title               VARCHAR(200)    NOT NULL,
    description         TEXT            NULL,
    resource_kind       ENUM('file', 'link') NOT NULL DEFAULT 'file',
    file_id             BIGINT UNSIGNED NULL,
    external_url        VARCHAR(500)    NULL,
    mime_category       ENUM('pdf', 'pptx', 'image', 'doc', 'other') NOT NULL DEFAULT 'other',
    sort_order          SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_by_user_id  BIGINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_section_resources_section (section_id, sort_order, created_at DESC),
    CONSTRAINT fk_section_resources_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_section_resources_file
        FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE SET NULL,
    CONSTRAINT fk_section_resources_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE practice_problems
    ADD COLUMN section_id INT UNSIGNED NULL AFTER course_id;

ALTER TABLE practice_problems
    ADD KEY idx_practice_problems_section (section_id),
    ADD CONSTRAINT fk_practice_problems_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE;

ALTER TABLE past_papers
    ADD COLUMN section_id INT UNSIGNED NULL AFTER course_id;

ALTER TABLE past_papers
    ADD KEY idx_past_papers_section (section_id),
    ADD CONSTRAINT fk_past_papers_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE;

ALTER TABLE section_announcement_comments
    ADD COLUMN parent_comment_id BIGINT UNSIGNED NULL AFTER announcement_id,
    ADD COLUMN is_pinned TINYINT(1) NOT NULL DEFAULT 0 AFTER body,
    ADD COLUMN pinned_by_user_id BIGINT UNSIGNED NULL AFTER is_pinned,
    ADD COLUMN pinned_at DATETIME(3) NULL AFTER pinned_by_user_id;

ALTER TABLE section_announcement_comments
    ADD KEY idx_announcement_comments_parent (parent_comment_id),
    ADD CONSTRAINT fk_announcement_comments_parent
        FOREIGN KEY (parent_comment_id) REFERENCES section_announcement_comments (id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_announcement_comments_pinner
        FOREIGN KEY (pinned_by_user_id) REFERENCES users (id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS section_grade_components (
    id                  INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NOT NULL,
    component_type        ENUM('ct', 'evaluation', 'attendance', 'portal', 'team') NOT NULL,
    label               VARCHAR(80)     NOT NULL,
    component_code      VARCHAR(40)     NOT NULL,
    max_score           DECIMAL(6,2)    NOT NULL DEFAULT 100.00,
    weight_percent      DECIMAL(5,2)    NOT NULL DEFAULT 0,
    portal_id           BIGINT UNSIGNED NULL,
    team_id             BIGINT UNSIGNED NULL,
    sort_order          SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_active           TINYINT(1)      NOT NULL DEFAULT 1,
    created_by_user_id  BIGINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_section_grade_components_code (section_id, component_code),
    KEY idx_section_grade_components_section (section_id, sort_order),
    CONSTRAINT fk_section_grade_components_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_section_grade_components_portal
        FOREIGN KEY (portal_id) REFERENCES assessment_portals (id) ON DELETE SET NULL,
    CONSTRAINT fk_section_grade_components_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE SET NULL,
    CONSTRAINT fk_section_grade_components_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE section_grades
    ADD COLUMN feedback TEXT NULL AFTER max_score;

CREATE TABLE IF NOT EXISTS grade_scales (
    id              TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    min_percent     DECIMAL(5,2)     NOT NULL,
    max_percent     DECIMAL(5,2)     NOT NULL,
    letter_grade    VARCHAR(5)       NOT NULL,
    gpa_points      DECIMAL(3,2)     NOT NULL,
    sort_order      TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    KEY idx_grade_scales_range (min_percent, max_percent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO grade_scales (min_percent, max_percent, letter_grade, gpa_points, sort_order) VALUES
    (93, 100, 'A+', 4.00, 1),
    (90, 92.99, 'A',  4.00, 2),
    (87, 89.99, 'A-', 3.70, 3),
    (83, 86.99, 'B+', 3.30, 4),
    (80, 82.99, 'B',  3.00, 5),
    (77, 79.99, 'B-', 2.70, 6),
    (73, 76.99, 'C+', 2.30, 7),
    (70, 72.99, 'C',  2.00, 8),
    (67, 69.99, 'C-', 1.70, 9),
    (60, 66.99, 'D',  1.00, 10),
    (0,  59.99, 'F',  0.00, 11);

CREATE TABLE IF NOT EXISTS student_semester_summaries (
    user_id         BIGINT UNSIGNED NOT NULL,
    semester_id     SMALLINT UNSIGNED NOT NULL,
    total_credits   DECIMAL(5,1)    NOT NULL DEFAULT 0,
    quality_points  DECIMAL(8,2)    NOT NULL DEFAULT 0,
    cgpa            DECIMAL(4,2)    NOT NULL DEFAULT 0,
    updated_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, semester_id),
    CONSTRAINT fk_semester_summaries_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_semester_summaries_semester
        FOREIGN KEY (semester_id) REFERENCES semesters (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE teams
    ADD COLUMN leader_user_id BIGINT UNSIGNED NULL AFTER created_by_user_id;

ALTER TABLE teams
    ADD CONSTRAINT fk_teams_leader
        FOREIGN KEY (leader_user_id) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE chat_groups
    ADD COLUMN team_id BIGINT UNSIGNED NULL AFTER section_id;

ALTER TABLE chat_groups
    ADD KEY idx_chat_groups_team (team_id),
    ADD CONSTRAINT fk_chat_groups_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE SET NULL;
