-- OpenDevOps Agent — initial schema
-- Requires PostgreSQL 13+ (gen_random_uuid() built-in, no extension needed)
-- Run: psql $DATABASE_URL -f migrations/001_initial.sql
--
-- LangGraph checkpointer tables (checkpoints, checkpoint_blobs, checkpoint_writes)
-- are created automatically by AsyncPostgresSaver.setup() — do NOT add them here.

-- ─────────────────────────────────────────────
-- organizations
-- Top-level tenant. A single-user install has one org.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- users
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID        REFERENCES organizations(id) ON DELETE CASCADE,
    email       TEXT        NOT NULL UNIQUE,
    name        TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS users_org_id_idx ON users(org_id);

-- ─────────────────────────────────────────────
-- aws_profiles
-- Per-org AWS connection configs for multi-account support (Phase 3).
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS aws_profiles (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID        REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    aws_region  TEXT        NOT NULL DEFAULT 'us-east-1',
    aws_profile TEXT,                      -- named profile in ~/.aws/credentials
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(org_id, name)
);

-- ─────────────────────────────────────────────
-- sessions
-- One session = one LangGraph thread_id. id IS the thread_id.
-- user_id / org_id are nullable so the app works before auth is wired up.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID        PRIMARY KEY,   -- same value as LangGraph thread_id
    user_id         UUID        REFERENCES users(id) ON DELETE SET NULL,
    org_id          UUID        REFERENCES organizations(id) ON DELETE SET NULL,
    aws_profile_id  UUID        REFERENCES aws_profiles(id) ON DELETE SET NULL,
    title           TEXT,                      -- auto-set from first user message (≤80 chars)
    model           TEXT        NOT NULL DEFAULT 'google/gemma-4-26b-a4b-it',
    aws_region      TEXT        NOT NULL DEFAULT 'us-east-1',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sessions_user_id_idx       ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_org_id_idx        ON sessions(org_id);
CREATE INDEX IF NOT EXISTS sessions_last_active_idx   ON sessions(last_active_at DESC);

-- ─────────────────────────────────────────────
-- messages
-- Every user and assistant message in a session.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}',  -- LangChain run_id, tags, RunnableConfig extras, etc.
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS messages_session_id_idx ON messages(session_id, created_at);

-- ─────────────────────────────────────────────
-- tool_calls
-- Every AWS tool invocation per agent turn.
-- message_id links to the assistant message that triggered the call.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tool_calls (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id  UUID        REFERENCES messages(id) ON DELETE SET NULL,
    tool_name   TEXT        NOT NULL,
    args        JSONB       NOT NULL DEFAULT '{}',
    result      JSONB,
    error       TEXT,                          -- non-null when tool returned an error
    duration_ms INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS tool_calls_session_id_idx ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS tool_calls_message_id_idx ON tool_calls(message_id);
CREATE INDEX IF NOT EXISTS tool_calls_tool_name_idx  ON tool_calls(tool_name);

-- ─────────────────────────────────────────────
-- usage_events
-- One row per completed agent turn: tokens, cost, latency.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id      UUID        REFERENCES messages(id) ON DELETE SET NULL,
    model           TEXT        NOT NULL,
    input_tokens    INTEGER     NOT NULL DEFAULT 0,
    output_tokens   INTEGER     NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(14, 8),            -- computed from pricing map
    latency_ms      INTEGER,
    tool_call_count INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS usage_events_session_id_idx ON usage_events(session_id);
CREATE INDEX IF NOT EXISTS usage_events_created_at_idx ON usage_events(created_at DESC);

-- ─────────────────────────────────────────────
-- findings
-- Structured root-cause analysis extracted from the agent's final answer.
-- Populated in Phase 2 when the agent returns a JSON findings block.
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS findings (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id           UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id           UUID        REFERENCES messages(id) ON DELETE SET NULL,
    root_cause_category  TEXT        CHECK (root_cause_category IN (
                             'SYSTEM_CHANGE', 'INPUT_ANOMALY', 'RESOURCE_LIMIT',
                             'COMPONENT_FAILURE', 'DEPENDENCY_ISSUE', 'UNKNOWN'
                         )),
    root_cause_summary   TEXT,
    confidence           TEXT        CHECK (confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    services_affected    TEXT[],
    mitigation_steps     TEXT[],
    evidence             TEXT[],
    raw_json             JSONB,                -- full structured output from agent
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS findings_session_id_idx ON findings(session_id);
CREATE INDEX IF NOT EXISTS findings_category_idx   ON findings(root_cause_category);

-- ─────────────────────────────────────────────
-- api_keys  (Phase 3 — programmatic / CLI access)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     UUID        REFERENCES users(id) ON DELETE SET NULL,
    name        TEXT        NOT NULL,
    key_hash    TEXT        NOT NULL UNIQUE,   -- bcrypt/sha256 hash, never store plaintext
    last_used_at TIMESTAMPTZ,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_keys_org_id_idx ON api_keys(org_id);
