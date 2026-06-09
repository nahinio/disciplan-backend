-- Extend practice_problems for Q/A content (frontend practice panel)

ALTER TABLE practice_problems
    ADD COLUMN question_text TEXT NULL AFTER title,
    ADD COLUMN answer_text TEXT NULL AFTER question_text;
