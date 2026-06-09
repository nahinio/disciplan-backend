-- Lookup rows for moderation (idempotent seeds).
INSERT IGNORE INTO reference_entity_types (code, label) VALUES
    ('blog_comment', 'Blog comment'),
    ('forum_reply',  'Forum reply');

INSERT IGNORE INTO report_reasons (code, label) VALUES
    ('inappropriate',       'Inappropriate content'),
    ('academic_dishonesty', 'Academic dishonesty');
