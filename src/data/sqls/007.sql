BEGIN;

ALTER TABLE settings ADD COLUMN speak_start_animation_enabled INTEGER DEFAULT 0;
ALTER TABLE settings ADD COLUMN speak_end_animation_enabled INTEGER DEFAULT 0;

COMMIT;