-- Persists event-driven investigation results for the Monitoring dashboard
CREATE TABLE IF NOT EXISTS alerts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    service       TEXT        NOT NULL,
    error         TEXT        NOT NULL,
    resolution    TEXT        NOT NULL DEFAULT '',
    confidence    TEXT        NOT NULL DEFAULT 'LOW'
                              CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    sns_sent      BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS alerts_created_at_idx ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS alerts_service_idx    ON alerts(service);
