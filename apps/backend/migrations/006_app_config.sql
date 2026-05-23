-- Stores application-level configuration such as init wizard and AWS event infra state
CREATE TABLE IF NOT EXISTS app_config (
    key        TEXT        PRIMARY KEY,
    value      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
