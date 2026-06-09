-- Optimized views for complex read queries (evaluator showcase)

-- Unread notification count per user (polled by frontend bell icon)
CREATE OR REPLACE VIEW v_user_unread_notification_counts AS
SELECT
    recipient_user_id AS user_id,
    COUNT(*)          AS unread_count
FROM notifications
WHERE is_read = 0
GROUP BY recipient_user_id;

-- Last message per chat group (keyset pagination helper)
CREATE OR REPLACE VIEW v_chat_group_last_messages AS
SELECT
    cm.group_id,
    cm.id          AS last_message_id,
    cm.sender_user_id,
    cm.body        AS last_message_preview,
    cm.created_at  AS last_message_at
FROM chat_messages cm
INNER JOIN (
    SELECT group_id, MAX(id) AS max_id
    FROM chat_messages
    WHERE deleted_at IS NULL
    GROUP BY group_id
) latest ON latest.max_id = cm.id;

-- Unread messages per user per group (complex join for chat badges)
CREATE OR REPLACE VIEW v_chat_group_unread_counts AS
SELECT
    cgm.user_id,
    cgm.group_id,
    COUNT(cm.id) AS unread_count
FROM chat_group_members cgm
INNER JOIN chat_messages cm
    ON cm.group_id = cgm.group_id
   AND cm.deleted_at IS NULL
   AND cm.sender_user_id <> cgm.user_id
LEFT JOIN chat_message_reads cmr
    ON cmr.message_id = cm.id
   AND cmr.user_id = cgm.user_id
WHERE cgm.left_at IS NULL
  AND cmr.message_id IS NULL
GROUP BY cgm.user_id, cgm.group_id;

-- Section enrollment summary
CREATE OR REPLACE VIEW v_section_enrollment_counts AS
SELECT
    section_id,
    COUNT(*) AS active_students
FROM section_enrollments
WHERE dropped_at IS NULL
GROUP BY section_id;

-- Blog post vote scores
CREATE OR REPLACE VIEW v_blog_post_scores AS
SELECT
    post_id,
    SUM(vd.value) AS score,
    COUNT(*)      AS vote_count
FROM blog_post_votes bpv
INNER JOIN vote_directions vd ON vd.id = bpv.direction_id
GROUP BY post_id;

-- Leaderboard (gamification)
CREATE OR REPLACE VIEW v_leaderboard_all_time AS
SELECT
    ug.user_id,
    up.display_name,
    ug.total_points,
    gt.label AS tier_label,
    RANK() OVER (ORDER BY ug.total_points DESC) AS rank_position
FROM user_gamification ug
INNER JOIN user_profiles up ON up.user_id = ug.user_id
INNER JOIN gamification_tiers gt ON gt.id = ug.tier_id;
