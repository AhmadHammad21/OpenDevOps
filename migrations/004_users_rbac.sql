-- RBAC: password auth + roles for users.
-- Idempotent: safe against both fresh DBs and the partial migration.

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

-- Drop and recreate constraint cleanly (handles the superadmin->admin,user change)
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin', 'user'));

CREATE INDEX IF NOT EXISTS users_role_idx ON users(role);

-- Cleanup from experimental work (owner_key was never in the canonical schema)
ALTER TABLE sessions  DROP COLUMN IF EXISTS owner_key;
DROP INDEX IF EXISTS sessions_owner_key_idx;
