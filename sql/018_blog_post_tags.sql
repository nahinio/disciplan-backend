-- Optional comma-style tags for blog posts (per course)

CREATE TABLE blog_tags (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    course_id   INT UNSIGNED    NOT NULL,
    name        VARCHAR(80)     NOT NULL,
    slug        VARCHAR(100)    NOT NULL,
    created_at  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_blog_tags_course_slug (course_id, slug),
    KEY idx_blog_tags_course (course_id),
    CONSTRAINT fk_blog_tags_course
        FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE blog_post_tags (
    post_id BIGINT UNSIGNED NOT NULL,
    tag_id  BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    KEY idx_blog_post_tags_tag (tag_id),
    CONSTRAINT fk_blog_post_tags_post
        FOREIGN KEY (post_id) REFERENCES blog_posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_blog_post_tags_tag
        FOREIGN KEY (tag_id) REFERENCES blog_tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
