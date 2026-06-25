-- Ranked hypotheses for a finding: list of {hypothesis, evidence[], confidence}.
-- Backfills empty for existing rows so older investigations still load.
ALTER TABLE findings ADD COLUMN IF NOT EXISTS hypotheses JSONB NOT NULL DEFAULT '[]';
