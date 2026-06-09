-- Optional cover image for blog posts
ALTER TABLE blog_posts
    ADD COLUMN cover_image_file_id BIGINT UNSIGNED NULL AFTER body_html,
    ADD CONSTRAINT fk_blog_posts_cover_image
        FOREIGN KEY (cover_image_file_id) REFERENCES files (id) ON DELETE SET NULL;
