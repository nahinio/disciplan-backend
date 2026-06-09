-- Achievement captions: how to earn each badge tier

ALTER TABLE achievement_definitions
    ADD COLUMN caption VARCHAR(255) NULL AFTER label;

UPDATE achievement_definitions SET caption = 'Have 1 content report you filed approved by moderators' WHERE code = 'moderator_1';
UPDATE achievement_definitions SET caption = 'Have 10 content reports you filed approved by moderators' WHERE code = 'moderator_2';
UPDATE achievement_definitions SET caption = 'Have 25 content reports you filed approved by moderators' WHERE code = 'moderator_3';
UPDATE achievement_definitions SET caption = 'Have 50 content reports you filed approved by moderators' WHERE code = 'moderator_4';
UPDATE achievement_definitions SET caption = 'Have 100 content reports you filed approved by moderators' WHERE code = 'moderator_5';

UPDATE achievement_definitions SET caption = 'Complete 100% of today''s planner tasks for 3 days in a row' WHERE code = 'iron_will_1';
UPDATE achievement_definitions SET caption = 'Complete 100% of today''s planner tasks for 7 days in a row' WHERE code = 'iron_will_2';
UPDATE achievement_definitions SET caption = 'Complete 100% of today''s planner tasks for 14 days in a row' WHERE code = 'iron_will_3';
UPDATE achievement_definitions SET caption = 'Complete 100% of today''s planner tasks for 30 days in a row' WHERE code = 'iron_will_4';
UPDATE achievement_definitions SET caption = 'Complete 100% of today''s planner tasks for 90 days in a row' WHERE code = 'iron_will_5';

UPDATE achievement_definitions SET caption = 'Have 1 doubt answer accepted as the official solution by faculty' WHERE code = 'faculty_favorite_1';
UPDATE achievement_definitions SET caption = 'Have 10 doubt answers accepted as official solutions by faculty' WHERE code = 'faculty_favorite_2';
UPDATE achievement_definitions SET caption = 'Have 25 doubt answers accepted as official solutions by faculty' WHERE code = 'faculty_favorite_3';
UPDATE achievement_definitions SET caption = 'Have 50 doubt answers accepted as official solutions by faculty' WHERE code = 'faculty_favorite_4';
UPDATE achievement_definitions SET caption = 'Have 100 doubt answers accepted as official solutions by faculty' WHERE code = 'faculty_favorite_5';

UPDATE achievement_definitions SET caption = 'Publish 1 blog post' WHERE code = 'master_author_1';
UPDATE achievement_definitions SET caption = 'Publish 5 blog posts' WHERE code = 'master_author_2';
UPDATE achievement_definitions SET caption = 'Publish 10 blog posts' WHERE code = 'master_author_3';
UPDATE achievement_definitions SET caption = 'Publish 25 blog posts' WHERE code = 'master_author_4';
UPDATE achievement_definitions SET caption = 'Publish 50 blog posts' WHERE code = 'master_author_5';

UPDATE achievement_definitions SET caption = 'Get 100 upvotes on one of your blog posts' WHERE code = 'catalyst_1';
UPDATE achievement_definitions SET caption = 'Get 250 upvotes on one of your blog posts' WHERE code = 'catalyst_2';
UPDATE achievement_definitions SET caption = 'Get 500 upvotes on one of your blog posts' WHERE code = 'catalyst_3';
UPDATE achievement_definitions SET caption = 'Get 1,000 upvotes on one of your blog posts' WHERE code = 'catalyst_4';
UPDATE achievement_definitions SET caption = 'Get 2,500 upvotes on one of your blog posts' WHERE code = 'catalyst_5';

UPDATE achievement_definitions SET caption = 'Finish 5 urgent/high-priority tasks within 2 hours of creating them' WHERE code = 'speedrunner_1';
UPDATE achievement_definitions SET caption = 'Finish 15 urgent/high-priority tasks within 2 hours of creating them' WHERE code = 'speedrunner_2';
UPDATE achievement_definitions SET caption = 'Finish 40 urgent/high-priority tasks within 2 hours of creating them' WHERE code = 'speedrunner_3';
UPDATE achievement_definitions SET caption = 'Finish 80 urgent/high-priority tasks within 2 hours of creating them' WHERE code = 'speedrunner_4';
UPDATE achievement_definitions SET caption = 'Finish 150 urgent/high-priority tasks within 2 hours of creating them' WHERE code = 'speedrunner_5';

UPDATE badge_types bt
INNER JOIN achievement_definitions ad ON ad.code = bt.code
SET bt.description = ad.caption
WHERE ad.caption IS NOT NULL;
