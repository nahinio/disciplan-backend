-- Practice problems: per-topic numbering and optional Cloudinary images

ALTER TABLE practice_problems
    ADD COLUMN problem_number SMALLINT UNSIGNED NULL AFTER topic_id,
    ADD COLUMN question_image_file_id BIGINT UNSIGNED NULL AFTER answer_text,
    ADD COLUMN answer_image_file_id BIGINT UNSIGNED NULL AFTER question_image_file_id,
    ADD KEY idx_practice_problems_topic_number (topic_id, problem_number);

ALTER TABLE practice_problems
    ADD CONSTRAINT fk_practice_problems_question_image
        FOREIGN KEY (question_image_file_id) REFERENCES files (id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_practice_problems_answer_image
        FOREIGN KEY (answer_image_file_id) REFERENCES files (id) ON DELETE SET NULL;
