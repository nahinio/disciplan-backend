-- =============================================================================
-- DisciPlan — Ultra-Normalized MySQL Schema (3NF / BCNF)
-- Raw SQL only — no ORM
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ── Lookup / reference tables ────────────────────────────────────────────────

CREATE TABLE roles (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(50)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_roles_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_statuses (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(50)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_statuses_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE departments (
    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)       NOT NULL,
    name        VARCHAR(120)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_departments_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE semesters (
    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)       NOT NULL,
    label       VARCHAR(80)       NOT NULL,
    starts_on   DATE              NOT NULL,
    ends_on     DATE              NOT NULL,
    is_current  TINYINT(1)        NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_semesters_code (code),
    CHECK (ends_on > starts_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE days_of_week (
    id          TINYINT UNSIGNED NOT NULL,
    code        CHAR(3)          NOT NULL,
    label       VARCHAR(12)      NOT NULL,
    sort_order  TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_days_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE notification_types (
    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(40)       NOT NULL,
    label       VARCHAR(80)       NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_notification_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE reference_entity_types (
    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(40)       NOT NULL,
    label       VARCHAR(80)       NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_reference_entity_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE file_storage_providers (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_file_storage_providers_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assessment_types (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_assessment_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE submission_statuses (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_submission_statuses_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE forum_thread_types (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_forum_thread_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_group_types (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_chat_group_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_member_roles (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_team_member_roles_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_invitation_statuses (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_team_invitation_statuses_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_action_types (
    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(40)       NOT NULL,
    label       VARCHAR(80)       NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_audit_action_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE blog_post_statuses (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_blog_post_statuses_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE author_roles (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_author_roles_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE vote_directions (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        CHAR(4)          NOT NULL,
    label       VARCHAR(20)      NOT NULL,
    value       TINYINT          NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_vote_directions_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE report_reasons (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(30)      NOT NULL,
    label       VARCHAR(80)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_report_reasons_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE report_statuses (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_report_statuses_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE task_priorities (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    sort_order  TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_task_priorities_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE energy_levels (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    label       VARCHAR(40)      NOT NULL,
    sort_order  TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_energy_levels_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE planner_task_types (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(40)      NOT NULL,
    label       VARCHAR(80)      NOT NULL,
    role_scope  ENUM('student', 'faculty', 'both') NOT NULL,
    sort_order  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_planner_task_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE gamification_tiers (
    id              TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code            VARCHAR(30)      NOT NULL,
    label           VARCHAR(60)      NOT NULL,
    min_points      INT UNSIGNED     NOT NULL,
    next_tier_id    TINYINT UNSIGNED NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_gamification_tiers_code (code),
    CONSTRAINT fk_gamification_tiers_next
        FOREIGN KEY (next_tier_id) REFERENCES gamification_tiers (id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Identity & auth ──────────────────────────────────────────────────────────

CREATE TABLE users (
    id              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    email           VARCHAR(255)     NOT NULL,
    password_hash   VARCHAR(255)     NOT NULL,
    role_id         TINYINT UNSIGNED NOT NULL,
    status_id       TINYINT UNSIGNED NOT NULL,
    email_verified  TINYINT(1)       NOT NULL DEFAULT 0,
    created_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    last_login_at   DATETIME(3)      NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role_status (role_id, status_id),
    CONSTRAINT fk_users_role
        FOREIGN KEY (role_id) REFERENCES roles (id),
    CONSTRAINT fk_users_status
        FOREIGN KEY (status_id) REFERENCES user_statuses (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_profiles (
    user_id         BIGINT UNSIGNED  NOT NULL,
    display_name    VARCHAR(120)     NOT NULL,
    department_id   SMALLINT UNSIGNED NULL,
    avatar_file_id  BIGINT UNSIGNED  NULL,
    avatar_preset   VARCHAR(40)      NULL,
    bio             VARCHAR(500)     NULL,
    created_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id),
    KEY idx_user_profiles_department (department_id),
    CONSTRAINT fk_user_profiles_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_profiles_department
        FOREIGN KEY (department_id) REFERENCES departments (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_preferences (
    user_id                     BIGINT UNSIGNED NOT NULL,
    theme                       VARCHAR(20)     NOT NULL DEFAULT 'system',
    notify_academic             TINYINT(1)      NOT NULL DEFAULT 1,
    notify_teams                TINYINT(1)      NOT NULL DEFAULT 1,
    notify_system               TINYINT(1)      NOT NULL DEFAULT 1,
    notify_messages             TINYINT(1)      NOT NULL DEFAULT 1,
    updated_at                  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id),
    CONSTRAINT fk_user_preferences_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE otp_verifications (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email           VARCHAR(255)    NOT NULL,
    code_hash       VARCHAR(255)    NOT NULL,
    expires_at      DATETIME(3)     NOT NULL,
    consumed_at     DATETIME(3)     NULL,
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_otp_email_expires (email, expires_at),
    KEY idx_otp_active (email, consumed_at, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE refresh_tokens (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NOT NULL,
    token_hash      CHAR(64)        NOT NULL,
    expires_at      DATETIME(3)     NOT NULL,
    revoked_at      DATETIME(3)     NULL,
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_refresh_tokens_hash (token_hash),
    KEY idx_refresh_tokens_user_active (user_id, revoked_at, expires_at),
    CONSTRAINT fk_refresh_tokens_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_gamification (
    user_id         BIGINT UNSIGNED  NOT NULL,
    tier_id         TINYINT UNSIGNED NOT NULL,
    total_points    INT UNSIGNED     NOT NULL DEFAULT 0,
    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id),
    KEY idx_user_gamification_tier_points (tier_id, total_points DESC),
    CONSTRAINT fk_user_gamification_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_gamification_tier
        FOREIGN KEY (tier_id) REFERENCES gamification_tiers (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE point_transactions (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NOT NULL,
    delta_points    INT             NOT NULL,
    reason_code     VARCHAR(40)     NOT NULL,
    reference_type  VARCHAR(40)     NULL,
    reference_id    BIGINT UNSIGNED NULL,
    created_at      DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_point_transactions_user_created (user_id, created_at DESC),
    CONSTRAINT fk_point_transactions_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── File metadata (binaries live on Cloudinary) ──────────────────────────────

CREATE TABLE files (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    storage_provider_id TINYINT UNSIGNED NOT NULL,
    storage_key         VARCHAR(255)     NOT NULL,
    secure_url          VARCHAR(512)     NOT NULL,
    original_filename   VARCHAR(255)     NOT NULL,
    mime_type           VARCHAR(120)     NOT NULL,
    size_bytes          BIGINT UNSIGNED  NOT NULL,
    checksum_sha256     CHAR(64)         NULL,
    width_px            INT UNSIGNED     NULL,
    height_px           INT UNSIGNED     NULL,
    uploaded_by_user_id BIGINT UNSIGNED  NOT NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)      NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_files_storage (storage_provider_id, storage_key),
    KEY idx_files_uploader_created (uploaded_by_user_id, created_at DESC),
    CONSTRAINT fk_files_provider
        FOREIGN KEY (storage_provider_id) REFERENCES file_storage_providers (id),
    CONSTRAINT fk_files_uploader
        FOREIGN KEY (uploaded_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE user_profiles
    ADD CONSTRAINT fk_user_profiles_avatar
        FOREIGN KEY (avatar_file_id) REFERENCES files (id) ON DELETE SET NULL;

-- ── Academic catalogue ───────────────────────────────────────────────────────

CREATE TABLE courses (
    id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    code            VARCHAR(20)      NOT NULL,
    title           VARCHAR(200)     NOT NULL,
    department_id   SMALLINT UNSIGNED NOT NULL,
    credit_hours    DECIMAL(3,1)     NOT NULL DEFAULT 3.0,
    has_project     TINYINT(1)       NOT NULL DEFAULT 0,
    is_active       TINYINT(1)       NOT NULL DEFAULT 1,
    created_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_courses_code (code),
    KEY idx_courses_department_active (department_id, is_active),
    CONSTRAINT fk_courses_department
        FOREIGN KEY (department_id) REFERENCES departments (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE sections (
    id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    course_id       INT UNSIGNED     NOT NULL,
    semester_id     SMALLINT UNSIGNED NOT NULL,
    section_label   CHAR(2)          NOT NULL,
    room            VARCHAR(40)      NULL,
    capacity        SMALLINT UNSIGNED NOT NULL DEFAULT 40,
    is_active       TINYINT(1)       NOT NULL DEFAULT 1,
    created_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_sections_course_semester_label (course_id, semester_id, section_label),
    KEY idx_sections_semester_active (semester_id, is_active),
    CONSTRAINT fk_sections_course
        FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_sections_semester
        FOREIGN KEY (semester_id) REFERENCES semesters (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_meeting_times (
    id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    section_id      INT UNSIGNED     NOT NULL,
    day_id          TINYINT UNSIGNED NOT NULL,
    starts_at       TIME             NOT NULL,
    ends_at         TIME             NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_section_meeting_slot (section_id, day_id, starts_at),
    KEY idx_section_meeting_day (day_id, section_id),
    CONSTRAINT fk_section_meeting_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_section_meeting_day
        FOREIGN KEY (day_id) REFERENCES days_of_week (id),
    CHECK (ends_at > starts_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_faculty (
    section_id      INT UNSIGNED     NOT NULL,
    faculty_user_id BIGINT UNSIGNED  NOT NULL,
    assigned_at     DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (section_id, faculty_user_id),
    KEY idx_section_faculty_user (faculty_user_id),
    CONSTRAINT fk_section_faculty_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_section_faculty_user
        FOREIGN KEY (faculty_user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_enrollments (
    id              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    section_id      INT UNSIGNED     NOT NULL,
    student_user_id BIGINT UNSIGNED  NOT NULL,
    enrolled_at     DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    dropped_at      DATETIME(3)      NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_section_enrollment_active (section_id, student_user_id, dropped_at),
    KEY idx_section_enrollments_student (student_user_id, dropped_at),
    CONSTRAINT fk_section_enrollments_section
        FOREIGN KEY (section_id) REFERENCES sections (id),
    CONSTRAINT fk_section_enrollments_student
        FOREIGN KEY (student_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Notifications (poll-based delivery) ──────────────────────────────────────

CREATE TABLE notifications (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    recipient_user_id   BIGINT UNSIGNED  NOT NULL,
    type_id             SMALLINT UNSIGNED NOT NULL,
    title               VARCHAR(200)     NOT NULL,
    body_preview        VARCHAR(300)     NULL,
    reference_type_id   SMALLINT UNSIGNED NULL,
    reference_id        BIGINT UNSIGNED  NULL,
    action_path         VARCHAR(300)     NULL,
    is_read             TINYINT(1)       NOT NULL DEFAULT 0,
    read_at             DATETIME(3)      NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_notifications_recipient_unread (recipient_user_id, is_read, created_at DESC),
    KEY idx_notifications_reference (reference_type_id, reference_id),
    CONSTRAINT fk_notifications_recipient
        FOREIGN KEY (recipient_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_type
        FOREIGN KEY (type_id) REFERENCES notification_types (id),
    CONSTRAINT fk_notifications_reference_type
        FOREIGN KEY (reference_type_id) REFERENCES reference_entity_types (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Section hub: announcements ─────────────────────────────────────────────

CREATE TABLE section_announcements (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NOT NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    title               VARCHAR(200)    NOT NULL,
    body                TEXT            NOT NULL,
    is_pinned           TINYINT(1)      NOT NULL DEFAULT 0,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_section_announcements_section_created (section_id, created_at DESC),
    KEY idx_section_announcements_pinned (section_id, is_pinned, created_at DESC),
    CONSTRAINT fk_section_announcements_section
        FOREIGN KEY (section_id) REFERENCES sections (id),
    CONSTRAINT fk_section_announcements_author
        FOREIGN KEY (author_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_announcement_comments (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    announcement_id     BIGINT UNSIGNED NOT NULL,
    parent_comment_id   BIGINT UNSIGNED NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    body                TEXT            NOT NULL,
    is_pinned           TINYINT(1)      NOT NULL DEFAULT 0,
    pinned_by_user_id   BIGINT UNSIGNED NULL,
    pinned_at           DATETIME(3)     NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_announcement_comments_announcement (announcement_id, created_at),
    KEY idx_announcement_comments_parent (parent_comment_id),
    CONSTRAINT fk_announcement_comments_announcement
        FOREIGN KEY (announcement_id) REFERENCES section_announcements (id) ON DELETE CASCADE,
    CONSTRAINT fk_announcement_comments_parent
        FOREIGN KEY (parent_comment_id) REFERENCES section_announcement_comments (id) ON DELETE SET NULL,
    CONSTRAINT fk_announcement_comments_author
        FOREIGN KEY (author_user_id) REFERENCES users (id),
    CONSTRAINT fk_announcement_comments_pinner
        FOREIGN KEY (pinned_by_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_resources (
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

-- ── Section hub: doubts (Q&A) ────────────────────────────────────────────────

CREATE TABLE section_doubts (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NOT NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    title               VARCHAR(200)    NOT NULL,
    body                TEXT            NOT NULL,
    is_verified         TINYINT(1)      NOT NULL DEFAULT 0,
    verified_by_user_id BIGINT UNSIGNED NULL,
    verified_at         DATETIME(3)     NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_section_doubts_section_created (section_id, created_at DESC),
    CONSTRAINT fk_section_doubts_section
        FOREIGN KEY (section_id) REFERENCES sections (id),
    CONSTRAINT fk_section_doubts_author
        FOREIGN KEY (author_user_id) REFERENCES users (id),
    CONSTRAINT fk_section_doubts_verifier
        FOREIGN KEY (verified_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_doubt_answers (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    doubt_id            BIGINT UNSIGNED NOT NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    body                TEXT            NOT NULL,
    is_faculty_answer   TINYINT(1)      NOT NULL DEFAULT 0,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_doubt_answers_doubt_created (doubt_id, created_at),
    CONSTRAINT fk_doubt_answers_doubt
        FOREIGN KEY (doubt_id) REFERENCES section_doubts (id) ON DELETE CASCADE,
    CONSTRAINT fk_doubt_answers_author
        FOREIGN KEY (author_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_doubt_votes (
    doubt_id            BIGINT UNSIGNED NOT NULL,
    voter_user_id       BIGINT UNSIGNED NOT NULL,
    direction_id        TINYINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (doubt_id, voter_user_id),
    CONSTRAINT fk_doubt_votes_doubt
        FOREIGN KEY (doubt_id) REFERENCES section_doubts (id) ON DELETE CASCADE,
    CONSTRAINT fk_doubt_votes_voter
        FOREIGN KEY (voter_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_doubt_votes_direction
        FOREIGN KEY (direction_id) REFERENCES vote_directions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Chat groups & messages (DB-backed, poll delivery) ────────────────────────

CREATE TABLE chat_groups (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED     NULL,
    team_id             BIGINT UNSIGNED  NULL,
    group_type_id       TINYINT UNSIGNED NOT NULL,
    name                VARCHAR(120)     NOT NULL,
    created_by_user_id  BIGINT UNSIGNED  NOT NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    is_active           TINYINT(1)       NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    KEY idx_chat_groups_section_active (section_id, is_active),
    CONSTRAINT fk_chat_groups_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE SET NULL,
    CONSTRAINT fk_chat_groups_type
        FOREIGN KEY (group_type_id) REFERENCES chat_group_types (id),
    CONSTRAINT fk_chat_groups_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_group_members (
    group_id            BIGINT UNSIGNED NOT NULL,
    user_id             BIGINT UNSIGNED NOT NULL,
    joined_at           DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    left_at             DATETIME(3)     NULL,
    PRIMARY KEY (group_id, user_id),
    KEY idx_chat_group_members_user_active (user_id, left_at),
    CONSTRAINT fk_chat_group_members_group
        FOREIGN KEY (group_id) REFERENCES chat_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_group_members_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_messages (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    group_id            BIGINT UNSIGNED NOT NULL,
    sender_user_id      BIGINT UNSIGNED NOT NULL,
    body                TEXT            NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    edited_at           DATETIME(3)     NULL,
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_chat_messages_group_cursor (group_id, id),
    KEY idx_chat_messages_group_created (group_id, created_at DESC),
    CONSTRAINT fk_chat_messages_group
        FOREIGN KEY (group_id) REFERENCES chat_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_messages_sender
        FOREIGN KEY (sender_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_message_reads (
    message_id          BIGINT UNSIGNED NOT NULL,
    user_id             BIGINT UNSIGNED NOT NULL,
    read_at             DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (message_id, user_id),
    KEY idx_chat_message_reads_user (user_id, read_at DESC),
    CONSTRAINT fk_chat_message_reads_message
        FOREIGN KEY (message_id) REFERENCES chat_messages (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_message_reads_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE chat_message_attachments (
    message_id          BIGINT UNSIGNED NOT NULL,
    file_id             BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (message_id, file_id),
    CONSTRAINT fk_chat_message_attachments_message
        FOREIGN KEY (message_id) REFERENCES chat_messages (id) ON DELETE CASCADE,
    CONSTRAINT fk_chat_message_attachments_file
        FOREIGN KEY (file_id) REFERENCES files (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Assessments, submissions, grades ─────────────────────────────────────────

CREATE TABLE assessment_portals (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED     NOT NULL,
    assessment_type_id  TINYINT UNSIGNED NOT NULL,
    title               VARCHAR(200)     NOT NULL,
    description         TEXT             NULL,
    opens_at            DATETIME(3)      NOT NULL,
    closes_at           DATETIME(3)      NOT NULL,
    max_score           DECIMAL(6,2)     NOT NULL DEFAULT 100.00,
    created_by_user_id  BIGINT UNSIGNED  NOT NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_assessment_portals_section_closes (section_id, closes_at),
    CONSTRAINT fk_assessment_portals_section
        FOREIGN KEY (section_id) REFERENCES sections (id),
    CONSTRAINT fk_assessment_portals_type
        FOREIGN KEY (assessment_type_id) REFERENCES assessment_types (id),
    CONSTRAINT fk_assessment_portals_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id),
    CHECK (closes_at > opens_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE submissions (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    portal_id           BIGINT UNSIGNED  NOT NULL,
    student_user_id     BIGINT UNSIGNED  NOT NULL,
    status_id           TINYINT UNSIGNED NOT NULL,
    submitted_at        DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    score               DECIMAL(6,2)     NULL,
    feedback            TEXT             NULL,
    graded_by_user_id   BIGINT UNSIGNED  NULL,
    graded_at           DATETIME(3)      NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_submissions_portal_student (portal_id, student_user_id),
    KEY idx_submissions_student_status (student_user_id, status_id),
    CONSTRAINT fk_submissions_portal
        FOREIGN KEY (portal_id) REFERENCES assessment_portals (id),
    CONSTRAINT fk_submissions_student
        FOREIGN KEY (student_user_id) REFERENCES users (id),
    CONSTRAINT fk_submissions_status
        FOREIGN KEY (status_id) REFERENCES submission_statuses (id),
    CONSTRAINT fk_submissions_grader
        FOREIGN KEY (graded_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE submission_files (
    submission_id       BIGINT UNSIGNED NOT NULL,
    file_id             BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (submission_id, file_id),
    CONSTRAINT fk_submission_files_submission
        FOREIGN KEY (submission_id) REFERENCES submissions (id) ON DELETE CASCADE,
    CONSTRAINT fk_submission_files_file
        FOREIGN KEY (file_id) REFERENCES files (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_grade_components (
    id                  INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NOT NULL,
    component_type      ENUM('ct', 'evaluation', 'attendance', 'portal', 'team') NOT NULL,
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
    CONSTRAINT fk_section_grade_components_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE section_grades (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NOT NULL,
    student_user_id     BIGINT UNSIGNED NOT NULL,
    component_code      VARCHAR(30)     NOT NULL,
    score               DECIMAL(6,2)    NOT NULL,
    max_score           DECIMAL(6,2)    NOT NULL DEFAULT 100.00,
    feedback            TEXT            NULL,
    recorded_by_user_id BIGINT UNSIGNED NOT NULL,
    recorded_at         DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_section_grades_component (section_id, student_user_id, component_code),
    KEY idx_section_grades_student (student_user_id, section_id),
    CONSTRAINT fk_section_grades_section
        FOREIGN KEY (section_id) REFERENCES sections (id),
    CONSTRAINT fk_section_grades_student
        FOREIGN KEY (student_user_id) REFERENCES users (id),
    CONSTRAINT fk_section_grades_recorder
        FOREIGN KEY (recorded_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Blogs ────────────────────────────────────────────────────────────────────

CREATE TABLE blog_posts (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    course_id           INT UNSIGNED     NOT NULL,
    topic_id            INT UNSIGNED     NULL,
    author_user_id      BIGINT UNSIGNED  NOT NULL,
    author_role_id      TINYINT UNSIGNED NOT NULL,
    status_id           TINYINT UNSIGNED NOT NULL,
    title               VARCHAR(250)     NOT NULL,
    slug                VARCHAR(280)     NOT NULL,
    excerpt             VARCHAR(500)     NULL,
    body_html           MEDIUMTEXT       NOT NULL,
    cover_image_file_id BIGINT UNSIGNED  NULL,
    read_time_min       SMALLINT UNSIGNED NOT NULL DEFAULT 5,
    is_verified         TINYINT(1)       NOT NULL DEFAULT 0,
    verified_by_user_id BIGINT UNSIGNED  NULL,
    verified_at         DATETIME(3)      NULL,
    is_pinned           TINYINT(1)       NOT NULL DEFAULT 0,
    published_at        DATETIME(3)      NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)      NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_blog_posts_course_slug (course_id, slug),
    KEY idx_blog_posts_course_published (course_id, published_at DESC),
    KEY idx_blog_posts_topic (topic_id),
    KEY idx_blog_posts_course_topic (course_id, topic_id),
    KEY idx_blog_posts_author (author_user_id, created_at DESC),
    CONSTRAINT fk_blog_posts_course
        FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_blog_posts_topic
        FOREIGN KEY (topic_id) REFERENCES syllabus_topics (id) ON DELETE SET NULL,
    CONSTRAINT fk_blog_posts_verified_by
        FOREIGN KEY (verified_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_blog_posts_author
        FOREIGN KEY (author_user_id) REFERENCES users (id),
    CONSTRAINT fk_blog_posts_author_role
        FOREIGN KEY (author_role_id) REFERENCES author_roles (id),
    CONSTRAINT fk_blog_posts_status
        FOREIGN KEY (status_id) REFERENCES blog_post_statuses (id),
    CONSTRAINT fk_blog_posts_cover_image
        FOREIGN KEY (cover_image_file_id) REFERENCES files (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE blog_post_votes (
    post_id             BIGINT UNSIGNED NOT NULL,
    voter_user_id       BIGINT UNSIGNED NOT NULL,
    direction_id        TINYINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (post_id, voter_user_id),
    CONSTRAINT fk_blog_post_votes_post
        FOREIGN KEY (post_id) REFERENCES blog_posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_blog_post_votes_voter
        FOREIGN KEY (voter_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_blog_post_votes_direction
        FOREIGN KEY (direction_id) REFERENCES vote_directions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE blog_comments (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    post_id             BIGINT UNSIGNED NOT NULL,
    parent_comment_id   BIGINT UNSIGNED NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    body                TEXT            NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_blog_comments_post_created (post_id, created_at),
    KEY idx_blog_comments_parent (parent_comment_id),
    CONSTRAINT fk_blog_comments_post
        FOREIGN KEY (post_id) REFERENCES blog_posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_blog_comments_parent
        FOREIGN KEY (parent_comment_id) REFERENCES blog_comments (id) ON DELETE SET NULL,
    CONSTRAINT fk_blog_comments_author
        FOREIGN KEY (author_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Course forum ─────────────────────────────────────────────────────────────

CREATE TABLE forum_threads (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    course_id           INT UNSIGNED     NOT NULL,
    author_user_id      BIGINT UNSIGNED  NOT NULL,
    thread_type_id      TINYINT UNSIGNED NOT NULL,
    title               VARCHAR(200)     NOT NULL,
    body                TEXT             NOT NULL,
    is_locked           TINYINT(1)       NOT NULL DEFAULT 0,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)      NULL,
    PRIMARY KEY (id),
    KEY idx_forum_threads_course_created (course_id, created_at DESC),
    CONSTRAINT fk_forum_threads_course
        FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_forum_threads_author
        FOREIGN KEY (author_user_id) REFERENCES users (id),
    CONSTRAINT fk_forum_threads_type
        FOREIGN KEY (thread_type_id) REFERENCES forum_thread_types (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE forum_thread_votes (
    thread_id           BIGINT UNSIGNED NOT NULL,
    voter_user_id       BIGINT UNSIGNED NOT NULL,
    direction_id        TINYINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (thread_id, voter_user_id),
    CONSTRAINT fk_forum_thread_votes_thread
        FOREIGN KEY (thread_id) REFERENCES forum_threads (id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_thread_votes_voter
        FOREIGN KEY (voter_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_thread_votes_direction
        FOREIGN KEY (direction_id) REFERENCES vote_directions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE forum_replies (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    thread_id           BIGINT UNSIGNED NOT NULL,
    parent_reply_id     BIGINT UNSIGNED NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    body                TEXT            NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME(3)      NULL,
    PRIMARY KEY (id),
    KEY idx_forum_replies_thread_created (thread_id, created_at),
    CONSTRAINT fk_forum_replies_thread
        FOREIGN KEY (thread_id) REFERENCES forum_threads (id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_replies_parent
        FOREIGN KEY (parent_reply_id) REFERENCES forum_replies (id) ON DELETE SET NULL,
    CONSTRAINT fk_forum_replies_author
        FOREIGN KEY (author_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE forum_reply_votes (
    reply_id            BIGINT UNSIGNED NOT NULL,
    voter_user_id       BIGINT UNSIGNED NOT NULL,
    direction_id        TINYINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (reply_id, voter_user_id),
    CONSTRAINT fk_forum_reply_votes_reply
        FOREIGN KEY (reply_id) REFERENCES forum_replies (id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_reply_votes_voter
        FOREIGN KEY (voter_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_reply_votes_direction
        FOREIGN KEY (direction_id) REFERENCES vote_directions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE forum_thread_attachments (
    thread_id           BIGINT UNSIGNED NOT NULL,
    file_id             BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (thread_id, file_id),
    CONSTRAINT fk_forum_thread_attachments_thread
        FOREIGN KEY (thread_id) REFERENCES forum_threads (id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_thread_attachments_file
        FOREIGN KEY (file_id) REFERENCES files (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Practice / syllabus ──────────────────────────────────────────────────────

CREATE TABLE syllabus_topics (
    id                  INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    course_id           INT UNSIGNED     NOT NULL,
    title               VARCHAR(200)     NOT NULL,
    week_number         TINYINT UNSIGNED NULL,
    sort_order          SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_syllabus_topics_course_title (course_id, title),
    KEY idx_syllabus_topics_course_order (course_id, sort_order),
    CONSTRAINT fk_syllabus_topics_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE grade_scales (
    id              TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    min_percent     DECIMAL(5,2)     NOT NULL,
    max_percent     DECIMAL(5,2)     NOT NULL,
    letter_grade    VARCHAR(5)       NOT NULL,
    gpa_points      DECIMAL(3,2)     NOT NULL,
    sort_order      TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    KEY idx_grade_scales_range (min_percent, max_percent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE student_semester_summaries (
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

CREATE TABLE practice_problems (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    course_id           INT UNSIGNED     NOT NULL,
    section_id          INT UNSIGNED     NULL,
    topic_id            INT UNSIGNED     NULL,
    assessment_type_id  TINYINT UNSIGNED NOT NULL,
    title               VARCHAR(200)     NOT NULL,
    difficulty_score    TINYINT UNSIGNED NOT NULL DEFAULT 3,
    created_by_user_id  BIGINT UNSIGNED  NOT NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_practice_problems_course_type (course_id, assessment_type_id),
    KEY idx_practice_problems_section (section_id),
    CONSTRAINT fk_practice_problems_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
    CONSTRAINT fk_practice_problems_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_practice_problems_topic
        FOREIGN KEY (topic_id) REFERENCES syllabus_topics (id) ON DELETE SET NULL,
    CONSTRAINT fk_practice_problems_type
        FOREIGN KEY (assessment_type_id) REFERENCES assessment_types (id),
    CONSTRAINT fk_practice_problems_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE past_papers (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    course_id           INT UNSIGNED    NOT NULL,
    section_id          INT UNSIGNED    NULL,
    title               VARCHAR(200)    NOT NULL,
    exam_year           SMALLINT UNSIGNED NOT NULL,
    file_id             BIGINT UNSIGNED NOT NULL,
    uploaded_by_user_id BIGINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_past_papers_course_year (course_id, exam_year DESC),
    KEY idx_past_papers_section (section_id),
    CONSTRAINT fk_past_papers_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
    CONSTRAINT fk_past_papers_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_past_papers_file
        FOREIGN KEY (file_id) REFERENCES files (id),
    CONSTRAINT fk_past_papers_uploader
        FOREIGN KEY (uploaded_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Project teams ────────────────────────────────────────────────────────────

CREATE TABLE teams (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    section_id          INT UNSIGNED    NULL,
    course_id           INT UNSIGNED    NOT NULL,
    name                VARCHAR(120)    NOT NULL,
    created_by_user_id          BIGINT UNSIGNED NOT NULL,
    leader_user_id              BIGINT UNSIGNED NULL,
    assigned_by_faculty_user_id BIGINT UNSIGNED NULL,
    created_at                  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    disbanded_at        DATETIME(3)     NULL,
    PRIMARY KEY (id),
    KEY idx_teams_course_active (course_id, disbanded_at),
    KEY idx_teams_section (section_id),
    CONSTRAINT fk_teams_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE SET NULL,
    CONSTRAINT fk_teams_course
        FOREIGN KEY (course_id) REFERENCES courses (id),
    CONSTRAINT fk_teams_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_teams_leader
        FOREIGN KEY (leader_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_teams_faculty_assigner
        FOREIGN KEY (assigned_by_faculty_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_members (
    team_id             BIGINT UNSIGNED  NOT NULL,
    user_id             BIGINT UNSIGNED  NOT NULL,
    role_id             TINYINT UNSIGNED NOT NULL,
    joined_at           DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    left_at             DATETIME(3)      NULL,
    PRIMARY KEY (team_id, user_id),
    KEY idx_team_members_user_active (user_id, left_at),
    CONSTRAINT fk_team_members_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT fk_team_members_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_team_members_role
        FOREIGN KEY (role_id) REFERENCES team_member_roles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_invitations (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    team_id             BIGINT UNSIGNED  NOT NULL,
    invitee_email       VARCHAR(255)     NOT NULL,
    invited_by_user_id  BIGINT UNSIGNED  NOT NULL,
    status_id           TINYINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    responded_at        DATETIME(3)      NULL,
    PRIMARY KEY (id),
    KEY idx_team_invitations_email_status (invitee_email, status_id),
    CONSTRAINT fk_team_invitations_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT fk_team_invitations_inviter
        FOREIGN KEY (invited_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_team_invitations_status
        FOREIGN KEY (status_id) REFERENCES team_invitation_statuses (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_tasks (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    team_id             BIGINT UNSIGNED  NOT NULL,
    title               VARCHAR(200)     NOT NULL,
    description         TEXT             NULL,
    assignee_user_id    BIGINT UNSIGNED  NULL,
    priority_id         TINYINT UNSIGNED NOT NULL,
    due_at              DATETIME(3)      NULL,
    is_completed        TINYINT(1)       NOT NULL DEFAULT 0,
    completed_at        DATETIME(3)      NULL,
    created_by_user_id  BIGINT UNSIGNED  NOT NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_team_tasks_team_due (team_id, due_at),
    KEY idx_team_tasks_assignee_open (assignee_user_id, is_completed),
    CONSTRAINT fk_team_tasks_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT fk_team_tasks_assignee
        FOREIGN KEY (assignee_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_team_tasks_priority
        FOREIGN KEY (priority_id) REFERENCES task_priorities (id),
    CONSTRAINT fk_team_tasks_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_important_dates (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    team_id             BIGINT UNSIGNED NOT NULL,
    label               VARCHAR(120)    NOT NULL,
    occurs_at           DATETIME(3)     NOT NULL,
    created_by_user_id  BIGINT UNSIGNED NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_team_dates_team_occurs (team_id, occurs_at),
    CONSTRAINT fk_team_dates_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT fk_team_dates_creator
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE team_announcements (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    team_id             BIGINT UNSIGNED NOT NULL,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    title               VARCHAR(200)    NOT NULL,
    body                TEXT            NOT NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_team_announcements_team_created (team_id, created_at DESC),
    CONSTRAINT fk_team_announcements_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
    CONSTRAINT fk_team_announcements_author
        FOREIGN KEY (author_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_pinned_teams (
    user_id             BIGINT UNSIGNED NOT NULL,
    team_id             BIGINT UNSIGNED NOT NULL,
    pinned_at           DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, team_id),
    CONSTRAINT fk_user_pinned_teams_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_pinned_teams_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Dashboard: tasks & calendar ──────────────────────────────────────────────

CREATE TABLE user_tasks (
    id                      BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    user_id                 BIGINT UNSIGNED  NOT NULL,
    course_id               INT UNSIGNED     NULL,
    assessment_type_id      TINYINT UNSIGNED NULL,
    planner_task_type_id    TINYINT UNSIGNED NULL,
    section_id              INT UNSIGNED     NULL,
    title                   VARCHAR(200)     NOT NULL,
    description             TEXT             NULL,
    attachment_file_id      BIGINT UNSIGNED  NULL,
    calendar_event_id       BIGINT UNSIGNED  NULL,
    scheduled_for_date      DATE             NULL,
    priority_id             TINYINT UNSIGNED NOT NULL,
    energy_level_id         TINYINT UNSIGNED NULL,
    estimated_effort_min    SMALLINT UNSIGNED NULL,
    computed_weight         DECIMAL(12,4)    NOT NULL DEFAULT 0,
    due_at                  DATETIME(3)      NULL,
    original_due_at         DATETIME(3)      NULL,
    is_completed            TINYINT(1)       NOT NULL DEFAULT 0,
    completion_percent      TINYINT UNSIGNED NOT NULL DEFAULT 0,
    completed_at            DATETIME(3)      NULL,
    is_skipped              TINYINT(1)       NOT NULL DEFAULT 0,
    skipped_at              DATETIME(3)      NULL,
    reschedule_count        SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    source                  VARCHAR(20)      NOT NULL DEFAULT 'manual',
    created_at              DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_user_tasks_user_due_open (user_id, is_completed, due_at),
    KEY idx_user_tasks_scheduled (user_id, scheduled_for_date, is_completed),
    KEY idx_user_tasks_source_day (user_id, source, scheduled_for_date),
    CONSTRAINT fk_user_tasks_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_tasks_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE SET NULL,
    CONSTRAINT fk_user_tasks_assessment_type
        FOREIGN KEY (assessment_type_id) REFERENCES assessment_types (id) ON DELETE SET NULL,
    CONSTRAINT fk_user_tasks_planner_type
        FOREIGN KEY (planner_task_type_id) REFERENCES planner_task_types (id) ON DELETE SET NULL,
    CONSTRAINT fk_user_tasks_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE SET NULL,
    CONSTRAINT fk_user_tasks_priority
        FOREIGN KEY (priority_id) REFERENCES task_priorities (id),
    CONSTRAINT fk_user_tasks_energy
        FOREIGN KEY (energy_level_id) REFERENCES energy_levels (id),
    CONSTRAINT fk_user_tasks_attachment
        FOREIGN KEY (attachment_file_id) REFERENCES files (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_daily_energy (
    user_id           BIGINT UNSIGNED  NOT NULL,
    energy_date       DATE             NOT NULL,
    energy_level_id   TINYINT UNSIGNED NOT NULL,
    set_at            DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, energy_date),
    CONSTRAINT fk_user_daily_energy_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_daily_energy_level
        FOREIGN KEY (energy_level_id) REFERENCES energy_levels (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_lecture_task_log (
    user_id         BIGINT UNSIGNED NOT NULL,
    section_id      INT UNSIGNED    NOT NULL,
    meeting_time_id INT UNSIGNED    NOT NULL,
    lecture_date    DATE            NOT NULL,
    task_id         BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (user_id, meeting_time_id, lecture_date),
    KEY idx_lecture_log_task (task_id),
    CONSTRAINT fk_lecture_log_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_lecture_log_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_lecture_log_meeting
        FOREIGN KEY (meeting_time_id) REFERENCES section_meeting_times (id) ON DELETE CASCADE,
    CONSTRAINT fk_lecture_log_task
        FOREIGN KEY (task_id) REFERENCES user_tasks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE calendar_events (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_user_id       BIGINT UNSIGNED NOT NULL,
    course_id           INT UNSIGNED    NULL,
    title               VARCHAR(200)    NOT NULL,
    description         TEXT            NULL,
    starts_at           DATETIME(3)     NOT NULL,
    ends_at             DATETIME(3)     NOT NULL,
    all_day             TINYINT(1)      NOT NULL DEFAULT 0,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_calendar_events_owner_range (owner_user_id, starts_at, ends_at),
    CONSTRAINT fk_calendar_events_owner
        FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_calendar_events_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE SET NULL,
    CHECK (ends_at >= starts_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE user_tasks
    ADD CONSTRAINT fk_user_tasks_calendar_event
        FOREIGN KEY (calendar_event_id) REFERENCES calendar_events (id) ON DELETE SET NULL;

-- ── Admin ────────────────────────────────────────────────────────────────────

CREATE TABLE global_announcements (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    author_user_id      BIGINT UNSIGNED NOT NULL,
    title               VARCHAR(200)    NOT NULL,
    body                TEXT            NOT NULL,
    is_active           TINYINT(1)      NOT NULL DEFAULT 1,
    scheduled_for       DATETIME(3)     NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_global_announcements_active_scheduled (is_active, scheduled_for),
    CONSTRAINT fk_global_announcements_author
        FOREIGN KEY (author_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE global_announcement_audiences (
    announcement_id     BIGINT UNSIGNED  NOT NULL,
    role_id             TINYINT UNSIGNED NOT NULL,
    PRIMARY KEY (announcement_id, role_id),
    CONSTRAINT fk_global_announcement_audiences_announcement
        FOREIGN KEY (announcement_id) REFERENCES global_announcements (id) ON DELETE CASCADE,
    CONSTRAINT fk_global_announcement_audiences_role
        FOREIGN KEY (role_id) REFERENCES roles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_logs (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    actor_user_id       BIGINT UNSIGNED  NULL,
    action_type_id      SMALLINT UNSIGNED NOT NULL,
    entity_type_id      SMALLINT UNSIGNED NULL,
    entity_id           BIGINT UNSIGNED  NULL,
    details_json        JSON             NULL,
    ip_address          VARCHAR(45)      NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_audit_logs_created (created_at DESC),
    KEY idx_audit_logs_actor (actor_user_id, created_at DESC),
    CONSTRAINT fk_audit_logs_actor
        FOREIGN KEY (actor_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_logs_action
        FOREIGN KEY (action_type_id) REFERENCES audit_action_types (id),
    CONSTRAINT fk_audit_logs_entity_type
        FOREIGN KEY (entity_type_id) REFERENCES reference_entity_types (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE content_reports (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    reporter_user_id    BIGINT UNSIGNED  NOT NULL,
    entity_type_id      SMALLINT UNSIGNED NOT NULL,
    entity_id           BIGINT UNSIGNED  NOT NULL,
    reason_id           TINYINT UNSIGNED NOT NULL,
    status_id           TINYINT UNSIGNED NOT NULL,
    notes               TEXT             NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    resolved_at         DATETIME(3)      NULL,
    resolved_by_user_id BIGINT UNSIGNED  NULL,
    PRIMARY KEY (id),
    KEY idx_content_reports_status_created (status_id, created_at DESC),
    CONSTRAINT fk_content_reports_reporter
        FOREIGN KEY (reporter_user_id) REFERENCES users (id),
    CONSTRAINT fk_content_reports_entity_type
        FOREIGN KEY (entity_type_id) REFERENCES reference_entity_types (id),
    CONSTRAINT fk_content_reports_reason
        FOREIGN KEY (reason_id) REFERENCES report_reasons (id),
    CONSTRAINT fk_content_reports_status
        FOREIGN KEY (status_id) REFERENCES report_statuses (id),
    CONSTRAINT fk_content_reports_resolver
        FOREIGN KEY (resolved_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE chat_groups
    ADD KEY idx_chat_groups_team (team_id),
    ADD CONSTRAINT fk_chat_groups_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE SET NULL;

ALTER TABLE section_grade_components
    ADD CONSTRAINT fk_section_grade_components_team
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE SET NULL;

SET FOREIGN_KEY_CHECKS = 1;
