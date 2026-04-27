"""Integration tests for POST /ask."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


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


def _mock_loop_result(answer="<p>ok</p>", tool_calls=None):
    return {"answer": answer, "tool_calls": tool_calls or []}


# ── happy path ────────────────────────────────────────────────────────────────

class TestAskHappyPath:
    def test_returns_html_answer(self, app_client):
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(return_value=_mock_loop_result("<p>Top artists</p>"))

        resp = tc.post("/ask", json={
            "prompt": "Who are my top artists?",
            "spotify_access_token": "tok_valid",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "<p>Top artists</p>" in data["answer"]
        assert data["conversation_id"] is not None

    def test_run_agentic_loop_invoked_once_per_request(self, app_client):
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(return_value=_mock_loop_result())

        tc.post("/ask", json={
            "prompt": "What are my top tracks?",
            "spotify_access_token": "tok",
        })
        assert oa.run_agentic_loop.call_count == 1

    def test_multi_tool_calls_are_surfaced(self, app_client):
        """The agentic loop can chain several tool calls before answering — verify
        that a multi-call result still flows through to the final answer untouched."""
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(return_value=_mock_loop_result(
            "<p>You're listening to Radiohead, one of your top artists.</p>",
            tool_calls=[
                {"tool": "get_current_playback", "parameters": {}, "result": {"track": "Karma Police"}},
                {"tool": "get_top_artists", "parameters": {"limit": 5}, "result": {"artists": ["Radiohead"]}},
            ],
        ))

        resp = tc.post("/ask", json={
            "prompt": "Is what I'm playing now one of my top artists?",
            "spotify_access_token": "tok",
        })
        assert resp.status_code == 200
        assert "Radiohead" in resp.json()["answer"]


# ── non-Spotify / general prompts ─────────────────────────────────────────────

class TestAskNonSpotify:
    def test_model_answers_directly_without_calling_tools(self, app_client):
        """When no tool call is needed, the model just answers — no canned guidance message."""
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(return_value=_mock_loop_result("<p>2 + 2 = 4</p>"))

        resp = tc.post("/ask", json={"prompt": "What is 2 + 2?"})
        assert resp.status_code == 200
        assert "4" in resp.json()["answer"]
        mock_tool.assert_not_called()


# ── missing access token ──────────────────────────────────────────────────────

class TestAskMissingToken:
    def test_no_tools_offered_without_token(self, app_client):
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(
            return_value=_mock_loop_result("<p>Please authenticate via /login first.</p>")
        )

        with patch("app.controller.app._get_user_id", return_value=None):
            resp = tc.post("/ask", json={"prompt": "Show my top artists"})

        assert resp.status_code == 200
        assert "login" in resp.json()["answer"].lower()
        mock_tool.assert_not_called()

        called_kwargs = oa.run_agentic_loop.call_args.kwargs
        assert called_kwargs["available_tools"] == []


# ── Spotify tool error ────────────────────────────────────────────────────────

class TestAskToolError:
    def test_error_is_incorporated_into_final_answer(self, app_client):
        """Tool errors are fed back into the loop as a tool message; the model
        explains the failure itself rather than the endpoint short-circuiting."""
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(return_value=_mock_loop_result(
            "<p>Sorry, there was an error reaching Spotify: Spotify API is unavailable.</p>",
            tool_calls=[{"tool": "get_top_artists", "parameters": {"limit": 5},
                         "result": {"error": "Spotify API is unavailable"}}],
        ))

        resp = tc.post("/ask", json={
            "prompt": "Top artists please",
            "spotify_access_token": "tok",
        })
        assert resp.status_code == 200
        assert "error" in resp.json()["answer"].lower()


# ── conversation persistence ──────────────────────────────────────────────────

class TestAskConversationPersistence:
    def test_same_conversation_id_reused(self, app_client, in_memory_db):
        tc, mock_tool, oa = app_client
        oa.run_agentic_loop = AsyncMock(return_value=_mock_loop_result("<p>ok</p>"))

        r1 = tc.post("/ask", json={"prompt": "Top artists", "spotify_access_token": "tok"})
        conv_id = r1.json()["conversation_id"]

        r2 = tc.post("/ask", json={
            "prompt": "Top tracks",
            "spotify_access_token": "tok",
            "conversation_id": conv_id,
        })
        assert r2.json()["conversation_id"] == conv_id
