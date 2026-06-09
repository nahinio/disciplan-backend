-- Admin-defined tags for practice problems (per course)

CREATE TABLE practice_tags (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    course_id   INT UNSIGNED    NOT NULL,
    name        VARCHAR(80)     NOT NULL,
    slug        VARCHAR(100)    NOT NULL,
    created_at  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_practice_tags_course_slug (course_id, slug),
    KEY idx_practice_tags_course (course_id),
    CONSTRAINT fk_practice_tags_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE practice_problem_tags (
    problem_id BIGINT UNSIGNED NOT NULL,
    tag_id     BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (problem_id, tag_id),
    KEY idx_practice_problem_tags_tag (tag_id),
    CONSTRAINT fk_practice_problem_tags_problem
        FOREIGN KEY (problem_id) REFERENCES practice_problems (id) ON DELETE CASCADE,
    CONSTRAINT fk_practice_problem_tags_tag
        FOREIGN KEY (tag_id) REFERENCES practice_tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
