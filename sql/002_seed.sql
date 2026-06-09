-- DisciPlan seed data — lookup tables only (no demo courses/users)

INSERT IGNORE INTO roles (code, label) VALUES
    ('student', 'Student'),
    ('faculty', 'Faculty'),
    ('admin',   'Administrator');

INSERT IGNORE INTO user_statuses (code, label) VALUES
    ('active',    'Active'),
    ('suspended', 'Suspended'),
    ('pending',   'Pending verification');

INSERT IGNORE INTO departments (code, name) VALUES
    ('CSE', 'Computer Science & Engineering'),
    ('BBA', 'Business Administration'),
    ('EEE', 'Electrical & Electronic Engineering');

INSERT IGNORE INTO semesters (code, label, starts_on, ends_on, is_current) VALUES
    ('2026-SPRING', 'Spring 2026', '2026-01-01', '2026-05-31', 1);

INSERT INTO days_of_week (id, code, label, sort_order) VALUES
    (0, 'SUN', 'Sunday',    0),
    (1, 'MON', 'Monday',    1),
    (2, 'TUE', 'Tuesday',   2),
    (3, 'WED', 'Wednesday', 3),
    (4, 'THU', 'Thursday',  4),
    (5, 'FRI', 'Friday',    5),
    (6, 'SAT', 'Saturday',  6);

INSERT INTO notification_types (code, label) VALUES
    ('new_message',       'New chat message'),
    ('new_announcement',  'New announcement'),
    ('doubt_answered',    'Doubt answered'),
    ('grade_posted',      'Grade posted'),
    ('team_invite',       'Team invitation'),
    ('submission_graded', 'Submission graded'),
    ('forum_reply',       'Forum reply'),
    ('system',            'System notification');

INSERT INTO reference_entity_types (code, label) VALUES
    ('message',      'Chat message'),
    ('announcement', 'Announcement'),
    ('doubt',        'Doubt'),
    ('submission',   'Submission'),
    ('team',         'Team'),
    ('blog_post',    'Blog post'),
    ('blog_comment', 'Blog comment'),
    ('forum_thread', 'Forum thread'),
    ('forum_reply',  'Forum reply'),
    ('user',         'User'),
    ('section',      'Section');

INSERT INTO file_storage_providers (code, label) VALUES
    ('cloudinary', 'Cloudinary');

INSERT INTO assessment_types (code, label) VALUES
    ('ct',     'Class Test'),
    ('mid',    'Mid Term'),
    ('final',  'Final Exam'),
    ('assign', 'Assignment'),
    ('quiz',   'Quiz');

INSERT INTO submission_statuses (code, label) VALUES
    ('pending',  'Pending'),
    ('submitted','Submitted'),
    ('late',     'Late'),
    ('graded',   'Graded'),
    ('missing',  'Missing');

INSERT INTO forum_thread_types (code, label) VALUES
    ('doubt',      'Doubt'),
    ('advice',     'Advice'),
    ('resource',   'Resource'),
    ('discussion', 'Discussion');

INSERT INTO chat_group_types (code, label) VALUES
    ('section', 'Section group'),
    ('project', 'Project group'),
    ('custom',  'Custom group');

INSERT INTO team_member_roles (code, label) VALUES
    ('leader', 'Team Leader'),
    ('member', 'Member');

INSERT INTO team_invitation_statuses (code, label) VALUES
    ('pending',  'Pending'),
    ('accepted', 'Accepted'),
    ('declined', 'Declined'),
    ('expired',  'Expired');

INSERT INTO audit_action_types (code, label) VALUES
    ('user_create',       'User created'),
    ('user_suspend',      'User suspended'),
    ('course_create',     'Course created'),
    ('section_create',    'Section created'),
    ('announcement_post', 'Announcement posted'),
    ('content_delete',    'Content deleted'),
    ('grade_record',      'Grade recorded'),
    ('system_reset',      'System reset');

INSERT INTO blog_post_statuses (code, label) VALUES
    ('draft',     'Draft'),
    ('published', 'Published'),
    ('archived',  'Archived');

INSERT INTO author_roles (code, label) VALUES
    ('student', 'Student'),
    ('faculty', 'Faculty'),
    ('admin',   'DisciPlan');

INSERT INTO vote_directions (code, label, value) VALUES
    ('up',   'Upvote',   1),
    ('down', 'Downvote', -1);

INSERT INTO report_reasons (code, label) VALUES
    ('spam',        'Spam'),
    ('harassment',  'Harassment'),
    ('misinfo',     'Misinformation'),
    ('off_topic',   'Off topic'),
    ('other',       'Other');

INSERT INTO report_statuses (code, label) VALUES
    ('open',     'Open'),
    ('reviewed', 'Reviewed'),
    ('resolved', 'Resolved'),
    ('dismissed','Dismissed');

INSERT INTO task_priorities (code, label, sort_order) VALUES
    ('low',    'Low',    1),
    ('medium', 'Medium', 2),
    ('high',   'High',   3),
    ('urgent', 'Urgent', 4);

INSERT INTO energy_levels (code, label, sort_order) VALUES
    ('low',    'Low energy',    1),
    ('medium', 'Medium energy', 2),
    ('high',   'High energy',   3);

INSERT IGNORE INTO planner_task_types (code, label, role_scope, sort_order) VALUES
    ('lecture',       'Lecture',        'both',    1),
    ('grading',       'Grading',        'faculty', 2),
    ('exam_quiz',     'Exam / Quiz',    'faculty', 3),
    ('meeting',       'Meeting',        'faculty', 4),
    ('personal',      'Personal',       'faculty', 5),
    ('ct',            'CT',             'student', 2),
    ('assignment',    'Assignment',     'student', 3),
    ('presentation',  'Presentation',   'student', 4),
    ('personal_goal', 'Personal goal',  'student', 5);

INSERT INTO gamification_tiers (id, code, label, min_points, next_tier_id) VALUES
    (1, 'bronze',   'Bronze Planner',   0,    NULL),
    (2, 'silver',   'Silver Planner',   500,  NULL),
    (3, 'gold',     'Gold Planner',     1500, NULL),
    (4, 'platinum', 'Platinum Planner', 3500, NULL);

UPDATE gamification_tiers SET next_tier_id = 2 WHERE id = 1;
UPDATE gamification_tiers SET next_tier_id = 3 WHERE id = 2;
UPDATE gamification_tiers SET next_tier_id = 4 WHERE id = 3;
