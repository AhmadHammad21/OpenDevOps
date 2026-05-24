-- Track which detection path triggered each alert
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS trigger_source TEXT;  -- 'poller' | 'event_consumer'

-- Per-alert, per-channel delivery log
CREATE TABLE IF NOT EXISTS alert_notifications (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id   UUID        NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    channel    TEXT        NOT NULL,                        -- 'slack' | 'sns' | 'telegram' | ...
    status     TEXT        NOT NULL DEFAULT 'attempted',    -- 'delivered' | 'failed' | 'attempted'
    error      TEXT,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_notifications_alert_id ON alert_notifications (alert_id);
