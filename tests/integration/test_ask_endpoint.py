"""Integration tests for POST /ask."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def _make_analysis(requires_spotify=True, tool="get_top_artists", parameters=None):
    return {
        "requires_spotify": requires_spotify,
        "tool": tool,
        "parameters": parameters or {"limit": 5},
        "reasoning": "test",
    }


@pytest.fixture()
def app_client(in_memory_db):
    """
    Full-stack TestClient: DB is in-memory; OpenAI and Spotify calls are mocked
    at the module level so the real app wiring is exercised.
    """
    with (
        patch("app.clients.open_ai_client.OpenAI"),
        patch("app.controller.app._get_user_id", return_value="user123"),
        patch("app.controller.app.execute_spotify_tool") as mock_tool,
        patch("app.database.init_db"),
    ):
        mock_tool.return_value = {"artists": [{"name": "Radiohead"}]}

        from app.clients.open_ai_client import OpenAIClient
        from app.controller.app import openai_client, spotify_tools
        openai_client.client = MagicMock()
        spotify_tools.get_available_tools = MagicMock(return_value=[])

        from fastapi.testclient import TestClient
        from app.controller.app import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_tool, openai_client


# ── happy path ────────────────────────────────────────────────────────────────

class TestAskHappyPath:
    def test_returns_html_answer(self, app_client):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis())
        oa.generate_spotify_enhanced_response = MagicMock(return_value="<p>Top artists</p>")

        resp = tc.post("/ask", json={
            "prompt": "Who are my top artists?",
            "spotify_access_token": "tok_valid",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "<p>Top artists</p>" in data["answer"]
        assert data["conversation_id"] is not None

    def test_executes_correct_tool(self, app_client):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis(tool="get_top_tracks"))
        oa.generate_spotify_enhanced_response = MagicMock(return_value="<p>Tracks</p>")

        tc.post("/ask", json={
            "prompt": "What are my top tracks?",
            "spotify_access_token": "tok",
        })
        called_tool = mock_tool.call_args[0][0]
        assert called_tool == "get_top_tracks"


# ── non-Spotify prompt ────────────────────────────────────────────────────────

class TestAskNonSpotify:
    def test_returns_guidance_message(self, app_client):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis(requires_spotify=False, tool=None))

        resp = tc.post("/ask", json={"prompt": "What is 2 + 2?"})
        assert resp.status_code == 200
        assert "Spotify" in resp.json()["answer"]
        mock_tool.assert_not_called()


# ── missing access token ──────────────────────────────────────────────────────

class TestAskMissingToken:
    def test_prompts_user_to_authenticate(self, app_client):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis())

        with patch("app.controller.app._get_user_id", return_value=None):
            resp = tc.post("/ask", json={"prompt": "Show my top artists"})

        assert resp.status_code == 200
        assert "access token" in resp.json()["answer"].lower()
        mock_tool.assert_not_called()


# ── Spotify tool error ────────────────────────────────────────────────────────

class TestAskToolError:
    def test_returns_error_message(self, app_client):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis())
        mock_tool.return_value = {"error": "Spotify API is unavailable"}

        resp = tc.post("/ask", json={
            "prompt": "Top artists please",
            "spotify_access_token": "tok",
        })
        assert resp.status_code == 200
        assert "error" in resp.json()["answer"].lower()


# ── no tool resolved ──────────────────────────────────────────────────────────

class TestAskNoTool:
    def test_returns_clarification_message(self, app_client):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis(tool=None))

        resp = tc.post("/ask", json={
            "prompt": "Do something with music",
            "spotify_access_token": "tok",
        })
        assert resp.status_code == 200
        assert mock_tool.call_count == 0


# ── conversation persistence ──────────────────────────────────────────────────

class TestAskConversationPersistence:
    def test_same_conversation_id_reused(self, app_client, in_memory_db):
        tc, mock_tool, oa = app_client
        oa.analyze_prompt = AsyncMock(return_value=_make_analysis())
        oa.generate_spotify_enhanced_response = MagicMock(return_value="<p>ok</p>")

        r1 = tc.post("/ask", json={"prompt": "Top artists", "spotify_access_token": "tok"})
        conv_id = r1.json()["conversation_id"]

        r2 = tc.post("/ask", json={
            "prompt": "Top tracks",
            "spotify_access_token": "tok",
            "conversation_id": conv_id,
        })
        assert r2.json()["conversation_id"] == conv_id
