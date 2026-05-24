-- Add dedup_key to alerts for cross-path deduplication (poller + event consumer)
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS dedup_key TEXT;
CREATE INDEX IF NOT EXISTS idx_alerts_dedup_key_created ON alerts (dedup_key, created_at DESC);
