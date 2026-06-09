-- Faculty accept student answer as official doubt solution

ALTER TABLE section_doubts
    ADD COLUMN accepted_answer_id BIGINT UNSIGNED NULL AFTER is_verified;

ALTER TABLE section_doubts
    ADD CONSTRAINT fk_section_doubts_accepted_answer
        FOREIGN KEY (accepted_answer_id) REFERENCES section_doubt_answers (id)
        ON DELETE SET NULL;

ALTER TABLE section_doubt_answers
    ADD COLUMN is_faculty_endorsed TINYINT(1) NOT NULL DEFAULT 0 AFTER is_faculty_answer;

INSERT IGNORE INTO notification_types (code, label) VALUES
    ('doubt_solution_accepted', 'Doubt solution accepted');

-- Backfill: verified student answers previously marked is_faculty_answer
UPDATE section_doubt_answers a
INNER JOIN section_doubts d ON d.id = a.doubt_id AND d.deleted_at IS NULL
INNER JOIN users u ON u.id = a.author_user_id
INNER JOIN roles r ON r.id = u.role_id
SET a.is_faculty_endorsed = 1,
    d.accepted_answer_id = COALESCE(d.accepted_answer_id, a.id)
WHERE d.is_verified = 1
  AND a.is_faculty_answer = 1
  AND a.deleted_at IS NULL
  AND r.code = 'student';

UPDATE section_doubt_answers a
INNER JOIN users u ON u.id = a.author_user_id
INNER JOIN roles r ON r.id = u.role_id
SET a.is_faculty_answer = 0
WHERE a.is_faculty_endorsed = 1
  AND r.code = 'student';
