-- Add metadata column to usage_events for tracking per-event context
-- (e.g. summarization flag, chars_removed, etc.)
ALTER TABLE usage_events
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
