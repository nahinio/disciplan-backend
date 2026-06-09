-- Course type (theory / lab) drives default class duration per section meeting.

CREATE TABLE course_types (
    id                TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code              VARCHAR(20)      NOT NULL,
    label             VARCHAR(40)      NOT NULL,
    duration_minutes  SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_course_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO course_types (code, label, duration_minutes) VALUES
    ('theory', 'Theory', 80),
    ('lab',    'Lab',    150);

ALTER TABLE courses
    ADD COLUMN course_type_id TINYINT UNSIGNED NOT NULL DEFAULT 1 AFTER credit_hours,
    ADD CONSTRAINT fk_courses_course_type
        FOREIGN KEY (course_type_id) REFERENCES course_types (id);
