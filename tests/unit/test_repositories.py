import pytest
from app import repositories


@pytest.fixture(autouse=True)
def use_in_memory_db(in_memory_db):
    pass


class TestCreateConversation:
    def test_returns_uuid_string(self):
        conv_id = repositories.create_conversation("user1", "Test")
        assert isinstance(conv_id, str) and len(conv_id) == 36

    def test_default_title(self):
        conv_id = repositories.create_conversation("user1")
        conv = repositories.get_conversation(conv_id)
        assert conv["title"] == "New conversation"

    def test_custom_title(self):
        conv_id = repositories.create_conversation("user1", "My Chat")
        conv = repositories.get_conversation(conv_id)
        assert conv["title"] == "My Chat"


class TestGetConversations:
    def test_returns_conversations_for_user(self):
        repositories.create_conversation("userA", "Chat 1")
        repositories.create_conversation("userA", "Chat 2")
        repositories.create_conversation("userB", "Other")
        convs = repositories.get_conversations("userA")
        assert len(convs) == 2

    def test_returns_empty_for_unknown_user(self):
        assert repositories.get_conversations("nobody") == []


class TestGetConversation:
    def test_returns_none_for_missing(self):
        assert repositories.get_conversation("nonexistent-id") is None

    def test_returns_dict_with_expected_keys(self):
        conv_id = repositories.create_conversation("user1", "Test")
        conv = repositories.get_conversation(conv_id)
        assert {"id", "user_id", "title"}.issubset(conv.keys())


class TestSaveAndGetMessages:
    def test_save_and_retrieve(self):
        conv_id = repositories.create_conversation("user1")
        repositories.save_message(conv_id, "user", "Hello")
        repositories.save_message(conv_id, "assistant", "Hi there")
        msgs = repositories.get_messages(conv_id)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_history_limit(self):
        conv_id = repositories.create_conversation("user1")
        for i in range(25):
            repositories.save_message(conv_id, "user", f"msg {i}")
        msgs = repositories.get_messages(conv_id)
        assert len(msgs) == 20  # HISTORY_LIMIT

    def test_returns_empty_for_empty_conversation(self):
        conv_id = repositories.create_conversation("user1")
        assert repositories.get_messages(conv_id) == []


class TestSetConversationTitle:
    def test_updates_title_when_default(self):
        conv_id = repositories.create_conversation("user1")
        repositories.set_conversation_title(conv_id, "Custom Title")
        assert repositories.get_conversation(conv_id)["title"] == "Custom Title"

    def test_does_not_overwrite_custom_title(self):
        conv_id = repositories.create_conversation("user1", "Already set")
        repositories.set_conversation_title(conv_id, "Should not apply")
        assert repositories.get_conversation(conv_id)["title"] == "Already set"


class TestDeleteConversation:
    def test_deletes_existing(self):
        conv_id = repositories.create_conversation("user1")
        repositories.delete_conversation(conv_id, "user1")
        assert repositories.get_conversation(conv_id) is None

    def test_noop_for_wrong_user(self):
        conv_id = repositories.create_conversation("user1")
        repositories.delete_conversation(conv_id, "wrong_user")
        assert repositories.get_conversation(conv_id) is not None
