import sqlite3
import tempfile
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

_SCHEMA = """
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
    CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
"""


def _make_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@pytest.fixture()
def in_memory_db(monkeypatch):
    """
    Redirect all DB operations to a temp-file SQLite database.
    A temp file (rather than :memory:) is used so the same DB is accessible
    from the TestClient's background thread.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = _make_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()

    factory = lambda: _make_connection(db_path)
    monkeypatch.setattr("app.database.get_connection", factory)
    monkeypatch.setattr("app.repositories.get_connection", factory)
    yield conn
    conn.close()
    os.unlink(db_path)


@pytest.fixture()
def client(in_memory_db):
    """FastAPI TestClient with a fresh DB and all external calls patched."""
    with (
        patch("app.controller.app.OpenAIClient") as MockOpenAI,
        patch("app.controller.app.SpotifyClient") as MockSpotify,
        patch("app.controller.app._get_user_id", return_value="user123"),
        patch("app.controller.app.execute_spotify_tool"),
        patch("app.database.init_db"),
    ):
        MockOpenAI.return_value.analyze_prompt.return_value = {
            "requires_spotify": True,
            "tool": "get_top_artists",
            "parameters": {"limit": 5},
            "reasoning": "top artists request",
        }
        MockOpenAI.return_value.generate_spotify_enhanced_response.return_value = "<p>Your top artists</p>"
        MockOpenAI.return_value.get_available_tools = lambda: []
        MockSpotify.return_value.get_available_tools.return_value = []
        MockSpotify.return_value.get_auth_url.return_value = "https://accounts.spotify.com/authorize?..."

        from app.controller.app import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
