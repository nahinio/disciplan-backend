-- Planner task management: types, weights, energy, lecture auto-tasks

CREATE TABLE IF NOT EXISTS planner_task_types (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(40)      NOT NULL,
    label       VARCHAR(80)      NOT NULL,
    role_scope  ENUM('student', 'faculty', 'both') NOT NULL,
    sort_order  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_planner_task_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO planner_task_types (code, label, role_scope, sort_order) VALUES
    ('lecture',       'Lecture',        'both',    1),
    ('grading',       'Grading',        'faculty', 2),
    ('exam_quiz',     'Exam / Quiz',    'faculty', 3),
    ('meeting',       'Meeting',        'faculty', 4),
    ('personal',      'Personal',       'faculty', 5),
    ('ct',            'CT',             'student', 2),
    ('assignment',    'Assignment',     'student', 3),
    ('presentation',  'Presentation',   'student', 4),
    ('personal_goal', 'Personal goal',  'student', 5);

ALTER TABLE user_tasks
    ADD COLUMN planner_task_type_id TINYINT UNSIGNED NULL AFTER assessment_type_id,
    ADD COLUMN section_id INT UNSIGNED NULL AFTER course_id,
    ADD COLUMN completion_percent TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER is_completed,
    ADD COLUMN estimated_effort_min SMALLINT UNSIGNED NULL AFTER energy_level_id,
    ADD COLUMN computed_weight DECIMAL(12,4) NOT NULL DEFAULT 0 AFTER estimated_effort_min,
    ADD COLUMN is_skipped TINYINT(1) NOT NULL DEFAULT 0 AFTER computed_weight,
    ADD COLUMN skipped_at DATETIME(3) NULL AFTER is_skipped,
    ADD COLUMN original_due_at DATETIME(3) NULL AFTER due_at,
    ADD COLUMN reschedule_count SMALLINT UNSIGNED NOT NULL DEFAULT 0 AFTER skipped_at,
    ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual' AFTER reschedule_count,
    ADD COLUMN attachment_file_id BIGINT UNSIGNED NULL AFTER description,
    ADD COLUMN calendar_event_id BIGINT UNSIGNED NULL AFTER attachment_file_id,
    ADD COLUMN scheduled_for_date DATE NULL AFTER calendar_event_id;

ALTER TABLE user_tasks
    ADD KEY idx_user_tasks_scheduled (user_id, scheduled_for_date, is_completed),
    ADD KEY idx_user_tasks_source_day (user_id, source, scheduled_for_date);

ALTER TABLE user_tasks
    ADD CONSTRAINT fk_user_tasks_planner_type
        FOREIGN KEY (planner_task_type_id) REFERENCES planner_task_types (id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_user_tasks_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_user_tasks_attachment
        FOREIGN KEY (attachment_file_id) REFERENCES files (id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_user_tasks_calendar_event
        FOREIGN KEY (calendar_event_id) REFERENCES calendar_events (id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS user_daily_energy (
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

CREATE TABLE IF NOT EXISTS user_lecture_task_log (
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
