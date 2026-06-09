-- Faculty self-signup verification queue (admin approve / reject)

CREATE TABLE IF NOT EXISTS faculty_verification_requests (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    user_id             BIGINT UNSIGNED  NOT NULL,
    email               VARCHAR(255)     NOT NULL,
    display_name        VARCHAR(120)     NOT NULL,
    status              VARCHAR(20)      NOT NULL DEFAULT 'pending',
    message             TEXT             NULL,
    reviewed_by_user_id BIGINT UNSIGNED  NULL,
    reviewed_at         DATETIME(3)      NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_fvr_status_created (status, created_at DESC),
    KEY idx_fvr_user (user_id),
    CONSTRAINT fk_fvr_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_fvr_reviewer
        FOREIGN KEY (reviewed_by_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
