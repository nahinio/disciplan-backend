-- Section schedule pattern (theory pairs or single lab day) + remove capacity.

ALTER TABLE sections
    ADD COLUMN schedule_key VARCHAR(20) NULL AFTER room;

ALTER TABLE sections
    DROP COLUMN capacity;
