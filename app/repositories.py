import uuid
import logging
from typing import List, Dict, Any, Optional
from .database import get_connection

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20


def create_conversation(user_id: str, title: str = "New conversation") -> str:
    conv_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
            (conv_id, user_id, title),
        )
    logger.info("Created conversation | id=%s | user=%s", conv_id, user_id)
    return conv_id


def get_conversations(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, title, created_at, updated_at
               FROM conversations
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    return dict(row) if row else None


def get_messages(conversation_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, role, content, created_at
               FROM messages
               WHERE conversation_id = ?
               ORDER BY created_at ASC""",
            (conversation_id,),
        ).fetchall()
    msgs = [dict(r) for r in rows]
    return msgs[-HISTORY_LIMIT:] if len(msgs) > HISTORY_LIMIT else msgs


def save_message(conversation_id: str, role: str, content: str) -> str:
    msg_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
            (msg_id, conversation_id, role, content),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )
    logger.info("Saved message | role=%s | conversation=%s", role, conversation_id)
    return msg_id


def set_conversation_title(conversation_id: str, title: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ? AND title = 'New conversation'",
            (title, conversation_id),
        )


def delete_conversation(conversation_id: str, user_id: str):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
    logger.info("Deleted conversation | id=%s | user=%s", conversation_id, user_id)
