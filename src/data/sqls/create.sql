BEGIN;

CREATE TABLE IF NOT EXISTS general_settings (
    id INTEGER PRIMARY KEY,
    autoconnect INTEGER DEFAULT 0,
    host TEXT DEFAULT '127.0.0.1',
    port INTEGER DEFAULT 12345,
    speak_start_animation_enabled INTEGER DEFAULT 0,
    speak_end_animation_enabled INTEGER DEFAULT 0
) STRICT;

CREATE TABLE IF NOT EXISTS teamspeak_settings (
    id INTEGER PRIMARY KEY,
    ip TEXT NOT NULL UNIQUE,
    port INTEGER NOT NULL,
    api TEXT NOT NULL,
    user_mute_behavior INTEGER DEFAULT 1
) STRICT;

CREATE TABLE IF NOT EXISTS obs_settings (
    id INTEGER PRIMARY KEY,
    ip TEXT NOT NULL UNIQUE,
    port INTEGER NOT NULL,
    password TEXT NOT NULL,
    low_blink_interval INTEGER DEFAULT 0,
    high_blink_interval INTEGER DEFAULT 0,
    blink_time INTEGER DEFAULT 0,
    blink_enabled INTEGER DEFAULT 0
) STRICT;

COMMIT;