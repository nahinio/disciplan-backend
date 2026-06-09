ALTER TABLE user_profiles
    ADD COLUMN avatar_preset VARCHAR(40) NULL AFTER avatar_file_id;
