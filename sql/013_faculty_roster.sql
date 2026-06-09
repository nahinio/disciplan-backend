-- Admin-pre-registered faculty emails; role assigned automatically on signup

CREATE TABLE IF NOT EXISTS faculty_roster (
    id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
    email               VARCHAR(255)     NOT NULL,
    display_name        VARCHAR(120)     NOT NULL,
    invited_by_user_id  BIGINT UNSIGNED  NULL,
    status              VARCHAR(20)      NOT NULL DEFAULT 'pending',
    claimed_user_id     BIGINT UNSIGNED  NULL,
    claimed_at          DATETIME(3)      NULL,
    created_at          DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_faculty_roster_email (email),
    KEY idx_faculty_roster_status (status, created_at DESC),
    CONSTRAINT fk_faculty_roster_inviter
        FOREIGN KEY (invited_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_faculty_roster_claimed_user
        FOREIGN KEY (claimed_user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
