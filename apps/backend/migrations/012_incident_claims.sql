-- Atomic incident claims used by poller and event consumer before agent runs
CREATE TABLE IF NOT EXISTS incident_claims (
    incident_key   TEXT        PRIMARY KEY,
    trigger_source TEXT        NOT NULL,
    status         TEXT        NOT NULL DEFAULT 'claimed', -- claimed | completed | failed
    session_id     UUID        REFERENCES sessions(id) ON DELETE SET NULL,
    claimed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incident_claims_claimed_at ON incident_claims (claimed_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_claims_status ON incident_claims (status);