import sqlite3
import logging
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "promptify.db"

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    logger.info("Initializing database at %s", DB_PATH)
    with get_connection() as conn:
        conn.executescript("""
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
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_user
                ON conversations(user_id);

            CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id);
        """)
    logger.info("Database ready")
