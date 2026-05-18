-- Distinguish event-triggered sessions from user-initiated chats
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'chat';
CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions (source);

-- Link alerts back to the session that produced them
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES sessions(id) ON DELETE SET NULL;
