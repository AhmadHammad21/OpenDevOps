-- Track whether a user has ever sent a message in an event-triggered session.
-- FALSE = auto-run only (hidden from sidebar); TRUE = user engaged (show in sidebar).
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_interacted BOOLEAN NOT NULL DEFAULT FALSE;
