-- Promptify database schema
-- Run this to recreate the database structure from scratch:
--   sqlite3 promptify.db < db/schema.sql
-- The application also runs this automatically on startup via init_db().

CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT 'New conversation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id);
