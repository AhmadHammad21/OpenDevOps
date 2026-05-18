-- Add status to alerts to distinguish completed vs failed investigations
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed';
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
