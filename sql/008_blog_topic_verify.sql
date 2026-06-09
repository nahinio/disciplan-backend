-- Topic-linked blogs with faculty verification
ALTER TABLE blog_posts
    ADD COLUMN topic_id INT UNSIGNED NULL AFTER course_id,
    ADD COLUMN is_verified TINYINT(1) NOT NULL DEFAULT 0 AFTER read_time_min,
    ADD COLUMN verified_by_user_id BIGINT UNSIGNED NULL AFTER is_verified,
    ADD COLUMN verified_at DATETIME(3) NULL AFTER verified_by_user_id;

ALTER TABLE blog_posts
    ADD KEY idx_blog_posts_topic (topic_id),
    ADD KEY idx_blog_posts_course_topic (course_id, topic_id),
    ADD CONSTRAINT fk_blog_posts_topic
        FOREIGN KEY (topic_id) REFERENCES syllabus_topics (id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_blog_posts_verified_by
        FOREIGN KEY (verified_by_user_id) REFERENCES users (id) ON DELETE SET NULL;
