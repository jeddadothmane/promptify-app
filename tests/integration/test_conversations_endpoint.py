"""Integration tests for conversation management endpoints."""
import pytest
from app import repositories


@pytest.fixture(autouse=True)
def use_in_memory_db(in_memory_db):
    pass


@pytest.fixture()
def tc(in_memory_db):
    from unittest.mock import patch
    with (
        patch("app.controller.app.OpenAIClient"),
        patch("app.controller.app.SpotifyClient"),
        patch("app.database.init_db"),
    ):
        from fastapi.testclient import TestClient
        from app.controller.app import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestListConversations:
    def test_returns_conversations_for_user(self, tc):
        repositories.create_conversation("userA", "Chat 1")
        repositories.create_conversation("userA", "Chat 2")
        repositories.create_conversation("userB", "Other")

        resp = tc.get("/conversations/userA")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_empty_list_for_unknown_user(self, tc):
        resp = tc.get("/conversations/nobody")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetConversationMessages:
    def test_returns_messages(self, tc):
        conv_id = repositories.create_conversation("userA", "Test")
        repositories.save_message(conv_id, "user", "Hello")
        repositories.save_message(conv_id, "assistant", "Hi")

        resp = tc.get(f"/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"

    def test_returns_404_for_unknown_conversation(self, tc):
        resp = tc.get("/conversations/nonexistent-id/messages")
        assert resp.status_code == 404


class TestDeleteConversation:
    def test_deletes_conversation(self, tc):
        conv_id = repositories.create_conversation("userA", "To delete")
        resp = tc.delete(f"/conversations/{conv_id}?user_id=userA")
        assert resp.status_code == 200
        assert repositories.get_conversation(conv_id) is None

    def test_returns_deleted_id(self, tc):
        conv_id = repositories.create_conversation("userA")
        resp = tc.delete(f"/conversations/{conv_id}?user_id=userA")
        assert resp.json()["deleted"] == conv_id
