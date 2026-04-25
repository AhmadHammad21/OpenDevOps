-- Soft delete support for sessions.
-- Deleted sessions are hidden from the UI but preserved for the 30-day cleanup job.
-- Safe to re-run (IF NOT EXISTS / IF column does not already exist via DO block).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sessions' AND column_name = 'is_deleted'
    ) THEN
        ALTER TABLE sessions ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sessions' AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE sessions ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS sessions_is_deleted_idx ON sessions(is_deleted) WHERE is_deleted = FALSE;
