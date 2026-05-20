-- Add evidence array and expose dedup_key from alerts
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS evidence TEXT NOT NULL DEFAULT '[]';
