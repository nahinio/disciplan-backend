-- Teams are assigned by faculty only (students cannot self-create).

ALTER TABLE teams
    ADD COLUMN assigned_by_faculty_user_id BIGINT UNSIGNED NULL AFTER leader_user_id;

ALTER TABLE teams
    ADD CONSTRAINT fk_teams_faculty_assigner
        FOREIGN KEY (assigned_by_faculty_user_id) REFERENCES users (id) ON DELETE SET NULL;

-- Backfill teams created by faculty/admin accounts.
UPDATE teams t
INNER JOIN users u ON u.id = t.created_by_user_id
INNER JOIN roles r ON r.id = u.role_id AND r.code IN ('faculty', 'admin')
SET t.assigned_by_faculty_user_id = t.created_by_user_id
WHERE t.assigned_by_faculty_user_id IS NULL;
