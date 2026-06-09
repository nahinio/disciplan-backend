-- Student section enrollment requests (admin approve / reject) + admin-managed enrollments

CREATE TABLE IF NOT EXISTS section_enrollment_requests (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    student_user_id     BIGINT UNSIGNED  NOT NULL,
    section_id          INT UNSIGNED     NOT NULL,
    status              VARCHAR(20)      NOT NULL DEFAULT 'pending',
    message             TEXT             NULL,
    reviewed_by_user_id BIGINT UNSIGNED  NULL,
    reviewed_at         DATETIME(3)      NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_ser_status_created (status, created_at DESC),
    KEY idx_ser_student (student_user_id, status),
    KEY idx_ser_section (section_id),
    CONSTRAINT fk_ser_student
        FOREIGN KEY (student_user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_ser_section
        FOREIGN KEY (section_id) REFERENCES sections (id) ON DELETE CASCADE,
    CONSTRAINT fk_ser_reviewer
        FOREIGN KEY (reviewed_by_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
