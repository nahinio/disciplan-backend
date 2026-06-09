CREATE OR REPLACE VIEW v_leaderboard_today AS
SELECT
    pt.user_id,
    up.display_name,
    SUM(pt.delta_points) AS today_points,
    RANK() OVER (ORDER BY SUM(pt.delta_points) DESC) AS rank_position
FROM point_transactions pt
INNER JOIN user_profiles up ON up.user_id = pt.user_id
WHERE DATE(pt.created_at) = UTC_DATE()
GROUP BY pt.user_id, up.display_name;
