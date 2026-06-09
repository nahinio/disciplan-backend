-- Planner event plans: divide tasks, recurrence, grading links

CREATE TABLE IF NOT EXISTS planner_event_plans (
    id                      BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    owner_user_id           BIGINT UNSIGNED  NOT NULL,
    title                   VARCHAR(200)     NOT NULL,
    description             TEXT             NULL,
    planner_task_type_id    TINYINT UNSIGNED NULL,
    course_id               INT UNSIGNED     NULL,
    section_id              INT UNSIGNED     NULL,
    scheduling_mode         ENUM(
        'deadline_divide',
        'grading_linked',
        'one_time',
        'recurring_weekly',
        'calendar_only'
    ) NOT NULL,
    deadline_at             DATETIME(3)      NULL,
    portal_id               BIGINT UNSIGNED  NULL,
    grade_component_id      BIGINT UNSIGNED  NULL,
    priority_id             TINYINT UNSIGNED NOT NULL,
    energy_level_id         TINYINT UNSIGNED NULL,
    estimated_effort_min    SMALLINT UNSIGNED NULL,
    plan_completed_percent  DECIMAL(5,2)     NOT NULL DEFAULT 0,
    is_active               TINYINT(1)       NOT NULL DEFAULT 1,
    is_completed            TINYINT(1)       NOT NULL DEFAULT 0,
    completed_at            DATETIME(3)      NULL,
    created_at              DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at              DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_planner_plans_owner_active (owner_user_id, is_active, scheduling_mode, deadline_at),
    CONSTRAINT fk_planner_plans_owner
        FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_planner_plans_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE SET NULL,
    CONSTRAINT fk_planner_plans_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE SET NULL,
    CONSTRAINT fk_planner_plans_type
        FOREIGN KEY (planner_task_type_id) REFERENCES planner_task_types (id) ON DELETE SET NULL,
    CONSTRAINT fk_planner_plans_priority
        FOREIGN KEY (priority_id) REFERENCES task_priorities (id),
    CONSTRAINT fk_planner_plans_energy
        FOREIGN KEY (energy_level_id) REFERENCES energy_levels (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS planner_event_recurrence (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    plan_id         BIGINT UNSIGNED NOT NULL,
    day_of_week     TINYINT UNSIGNED NOT NULL,
    starts_time     TIME            NOT NULL,
    duration_min    SMALLINT UNSIGNED NOT NULL DEFAULT 60,
    PRIMARY KEY (id),
    KEY idx_recurrence_plan (plan_id),
    CONSTRAINT fk_recurrence_plan
        FOREIGN KEY (plan_id) REFERENCES planner_event_plans (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO planner_task_types (code, label, role_scope, sort_order) VALUES
    ('lecture_prep', 'Lecture preparation', 'faculty', 1),
    ('one_time',     'One-time task',     'both',    6);
