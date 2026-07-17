import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture()
def client():
    with patch("app.clients.open_ai_client.OpenAI"):
        from app.clients.open_ai_client import OpenAIClient
        c = OpenAIClient()
        c.client = MagicMock()
        return c


# ── _spotify_tools_to_openai_schema ───────────────────────────────────────────

class TestSpotifyToolsToOpenAISchema:
    def test_required_param_has_no_default(self, client):
        schema = client._spotify_tools_to_openai_schema([
            {"name": "search_tracks", "description": "Search for tracks",
             "parameters": {"query": {"type": "string", "description": "Search query"}}}
        ])
        fn = schema[0]["function"]
        assert fn["name"] == "search_tracks"
        assert fn["parameters"]["required"] == ["query"]
        assert fn["parameters"]["properties"]["query"]["type"] == "string"

    def test_param_with_default_is_not_required(self, client):
        schema = client._spotify_tools_to_openai_schema([
            {"name": "get_top_artists", "description": "Get top artists",
             "parameters": {"limit": {"type": "integer", "default": 5, "description": "count"}}}
        ])
        assert schema[0]["function"]["parameters"]["required"] == []

    def test_no_params_tool(self, client):
        schema = client._spotify_tools_to_openai_schema([
            {"name": "get_current_playback", "description": "Current playback", "parameters": {}}
        ])
        assert schema[0]["function"]["parameters"]["properties"] == {}
        assert schema[0]["function"]["parameters"]["required"] == []


# ── run_agentic_loop ───────────────────────────────────────────────────────────

def _completion_with_content(content: str):
    response_mock = MagicMock()
    response_mock.choices[0].message.content = content
    response_mock.choices[0].message.tool_calls = None
    return response_mock


def _completion_with_tool_call(tool_call_id: str, name: str, arguments: dict):
    tool_call = MagicMock()
    tool_call.id = tool_call_id
    tool_call.function.name = name
    tool_call.function.arguments = json.dumps(arguments)

    response_mock = MagicMock()
    response_mock.choices[0].message.content = None
    response_mock.choices[0].message.tool_calls = [tool_call]
    return response_mock


class TestRunAgenticLoop:
    @pytest.mark.asyncio
    async def test_answers_directly_without_calling_any_tool(self, client):
        client.client.chat.completions.create.return_value = _completion_with_content("The capital of France is Paris.")
        execute_tool = AsyncMock()

        result = await client.run_agentic_loop(
            prompt="What is the capital of France?",
            available_tools=[],
            execute_tool=execute_tool,
            system_message="You are a helpful assistant.",
        )

        assert result["answer"] == "The capital of France is Paris."
        assert result["tool_calls"] == []
        execute_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_tool_call_then_final_answer(self, client):
        client.client.chat.completions.create.side_effect = [
            _completion_with_tool_call("call_1", "get_top_artists", {"limit": 5}),
            _completion_with_content("<p>Your top artist is Radiohead.</p>"),
        ]
        execute_tool = AsyncMock(return_value={"artists": [{"name": "Radiohead"}]})

        result = await client.run_agentic_loop(
            prompt="Who are my top artists?",
            available_tools=[{"name": "get_top_artists", "description": "", "parameters": {}}],
            execute_tool=execute_tool,
            system_message="You are a helpful assistant.",
        )

        assert "Radiohead" in result["answer"]
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "get_top_artists"
        execute_tool.assert_awaited_once_with("get_top_artists", {"limit": 5})

    @pytest.mark.asyncio
    async def test_chains_multiple_tool_calls_across_turns(self, client):
        client.client.chat.completions.create.side_effect = [
            _completion_with_tool_call("call_1", "get_current_playback", {}),
            _completion_with_tool_call("call_2", "get_top_artists", {"limit": 5}),
            _completion_with_content("<p>Yes, that's one of your top artists.</p>"),
        ]
        execute_tool = AsyncMock(side_effect=[
            {"track": "Karma Police", "artist": "Radiohead"},
            {"artists": [{"name": "Radiohead"}]},
        ])

        result = await client.run_agentic_loop(
            prompt="Is what's playing one of my top artists?",
            available_tools=[
                {"name": "get_current_playback", "description": "", "parameters": {}},
                {"name": "get_top_artists", "description": "", "parameters": {}},
            ],
            execute_tool=execute_tool,
            system_message="You are a helpful assistant.",
        )

        assert len(result["tool_calls"]) == 2
        assert [c["tool"] for c in result["tool_calls"]] == ["get_current_playback", "get_top_artists"]
        assert execute_tool.await_count == 2

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_a_single_turn(self, client):
        tool_call_1 = MagicMock()
        tool_call_1.id = "call_1"
        tool_call_1.function.name = "get_top_artists"
        tool_call_1.function.arguments = json.dumps({"limit": 5})

        tool_call_2 = MagicMock()
        tool_call_2.id = "call_2"
        tool_call_2.function.name = "get_top_tracks"
        tool_call_2.function.arguments = json.dumps({"limit": 5})

        first_response = MagicMock()
        first_response.choices[0].message.content = None
        first_response.choices[0].message.tool_calls = [tool_call_1, tool_call_2]

        client.client.chat.completions.create.side_effect = [
            first_response,
            _completion_with_content("<p>Here's both.</p>"),
        ]
        execute_tool = AsyncMock(side_effect=[
            {"artists": [{"name": "Radiohead"}]},
            {"tracks": [{"name": "Karma Police"}]},
        ])

        result = await client.run_agentic_loop(
            prompt="Give me my top artists and tracks",
            available_tools=[],
            execute_tool=execute_tool,
            system_message="You are a helpful assistant.",
        )

        assert len(result["tool_calls"]) == 2
        assert execute_tool.await_count == 2

    @pytest.mark.asyncio
    async def test_stops_after_max_iterations_and_forces_final_answer(self, client):
        looping_response = _completion_with_tool_call("call_1", "search_tracks", {"query": "test"})
        client.client.chat.completions.create.side_effect = [
            looping_response, looping_response, looping_response,
            _completion_with_content("<p>Giving up gracefully.</p>"),
        ]
        execute_tool = AsyncMock(return_value={"tracks": []})

        result = await client.run_agentic_loop(
            prompt="find me something",
            available_tools=[{"name": "search_tracks", "description": "", "parameters": {}}],
            execute_tool=execute_tool,
            system_message="You are a helpful assistant.",
            max_iterations=3,
        )

        assert result["answer"] == "<p>Giving up gracefully.</p>"
        assert execute_tool.await_count == 3
        assert client.client.chat.completions.create.call_count == 4


# ── generate_playlist_plan ────────────────────────────────────────────────────

class TestGeneratePlaylistPlan:
    def test_happy_path(self, client):
        payload = {
            "name": "Workout Beats",
            "description": "High energy",
            "tracks": [{"title": "Eye of the Tiger", "artist": "Survivor"}] * 5,
        }
        response_mock = MagicMock()
        response_mock.choices[0].message.content = json.dumps(payload)
        client.client.chat.completions.create.return_value = response_mock

        plan = client.generate_playlist_plan("workout playlist", 5)
        assert plan["name"] == "Workout Beats"
        assert len(plan["tracks"]) == 5

    def test_returns_fallback_on_api_error(self, client):
        client.client.chat.completions.create.side_effect = Exception("fail")
        plan = client.generate_playlist_plan("chill vibes", 10)
        assert "name" in plan
        assert plan["tracks"] == []
