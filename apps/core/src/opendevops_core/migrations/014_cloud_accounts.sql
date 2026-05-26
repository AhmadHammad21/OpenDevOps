-- Provider-agnostic cloud account connections (AWS / GCP / Azure).
-- Supersedes the AWS-only aws_profiles table (left in place; migrations are append-only).
--
-- org_id NULL  = single-tenant / OSS (one set of accounts for the whole install).
-- org_id set   = multi-tenant / product (per-org accounts).
-- No rows at all = fall back to env/profile credentials (current OSS behavior).
--
-- `config` holds NON-secret provider-specific fields (role ARN, project id, region, etc.).
-- Secrets (external id, raw keys, SA JSON, client secret) go encrypted in `secret_enc`.
CREATE TABLE IF NOT EXISTS cloud_accounts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID        REFERENCES organizations(id) ON DELETE CASCADE,
    provider      TEXT        NOT NULL DEFAULT 'aws',    -- 'aws' | 'gcp' | 'azure'
    auth_method   TEXT        NOT NULL,                  -- e.g. 'assume_role' | 'access_key'
    label         TEXT        NOT NULL,
    region        TEXT,                                  -- generic region / location
    config        JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- non-secret provider fields
    secret_enc    TEXT,                                  -- Fernet-encrypted secret blob (nullable)
    status        TEXT        NOT NULL DEFAULT 'pending', -- 'pending' | 'verified' | 'error'
    status_detail TEXT,                                  -- last verify result (caller identity / error)
    is_default    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cloud_accounts_org_idx ON cloud_accounts (org_id);

-- At most one default account per (org, provider). COALESCE folds the NULL (OSS) org
-- into a fixed sentinel so the partial unique index also constrains single-tenant rows.
CREATE UNIQUE INDEX IF NOT EXISTS cloud_accounts_default_idx
    ON cloud_accounts (COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid), provider)
    WHERE is_default;
