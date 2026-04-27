import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture()
def client():
    with patch("app.clients.open_ai_client.OpenAI"):
        from app.clients.open_ai_client import OpenAIClient
        c = OpenAIClient()
        c.client = MagicMock()
        return c


# ── fallback_keyword_detection ────────────────────────────────────────────────

class TestFallbackKeywordDetection:
    def test_top_artists(self, client):
        result = client.fallback_keyword_detection("Show me my top artists")
        assert result["tool"] == "get_top_artists"

    def test_top_artists_limit_extracted(self, client):
        result = client.fallback_keyword_detection("Who are my top 10 favorite artists?")
        assert result["tool"] == "get_top_artists"
        assert result["parameters"]["limit"] == 10

    def test_top_tracks(self, client):
        result = client.fallback_keyword_detection("Show my top tracks")
        assert result["tool"] == "get_top_tracks"

    def test_recently_played(self, client):
        result = client.fallback_keyword_detection("What did I recently played?")
        assert result["tool"] == "get_recently_played"

    def test_current_playback(self, client):
        result = client.fallback_keyword_detection("What's playing right now?")
        assert result["tool"] == "get_current_playback"
        assert result["parameters"] == {}

    def test_create_playlist(self, client):
        prompt = "Create a playlist for me"
        result = client.fallback_keyword_detection(prompt)
        assert result["tool"] == "create_playlist_from_prompt"
        assert result["parameters"]["prompt"] == prompt

    def test_get_user_playlists(self, client):
        result = client.fallback_keyword_detection("Show my playlists")
        assert result["tool"] == "get_user_playlists"

    def test_search_tracks(self, client):
        result = client.fallback_keyword_detection("Search for Radiohead")
        assert result["tool"] == "search_tracks"

    def test_no_match_returns_none(self, client):
        result = client.fallback_keyword_detection("What is the capital of France?")
        assert result["tool"] is None


# ── _fallback_full_analysis ───────────────────────────────────────────────────

class TestFallbackFullAnalysis:
    def test_non_spotify_prompt(self, client):
        result = client._fallback_full_analysis("What is 2 + 2?")
        assert result["requires_spotify"] is False
        assert result["tool"] is None

    def test_spotify_prompt_delegates_to_keyword(self, client):
        result = client._fallback_full_analysis("Show my top artists")
        assert result["requires_spotify"] is True
        assert result["tool"] == "get_top_artists"


# ── analyze_prompt ────────────────────────────────────────────────────────────

class TestAnalyzePrompt:
    def _mock_completion(self, client, payload: dict):
        response_mock = MagicMock()
        response_mock.choices[0].message.content = json.dumps(payload)
        client.client.chat.completions.create.return_value = response_mock

    @pytest.mark.asyncio
    async def test_happy_path(self, client):
        self._mock_completion(client, {
            "requires_spotify": True,
            "tool": "get_top_tracks",
            "parameters": {"limit": 5},
            "reasoning": "user wants top tracks",
        })
        result = await client.analyze_prompt("my top tracks", [])
        assert result["requires_spotify"] is True
        assert result["tool"] == "get_top_tracks"

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, client):
        raw = "```json\n" + json.dumps({
            "requires_spotify": True,
            "tool": "get_current_playback",
            "parameters": {},
            "reasoning": "playback",
        }) + "\n```"
        response_mock = MagicMock()
        response_mock.choices[0].message.content = raw
        client.client.chat.completions.create.return_value = response_mock

        result = await client.analyze_prompt("what's playing", [])
        assert result["tool"] == "get_current_playback"

    @pytest.mark.asyncio
    async def test_falls_back_on_invalid_json(self, client):
        response_mock = MagicMock()
        response_mock.choices[0].message.content = "not json at all"
        client.client.chat.completions.create.return_value = response_mock

        result = await client.analyze_prompt("Show my top artists", [])
        # Fallback should still return a coherent structure
        assert "requires_spotify" in result

    @pytest.mark.asyncio
    async def test_falls_back_on_api_exception(self, client):
        client.client.chat.completions.create.side_effect = Exception("network error")
        result = await client.analyze_prompt("my top artists", [])
        assert "requires_spotify" in result


# ── generate_spotify_enhanced_response ───────────────────────────────────────

class TestGenerateSpotifyEnhancedResponse:
    def test_returns_raw_html(self, client):
        response_mock = MagicMock()
        response_mock.choices[0].message.content = "<ul><li>Artist 1</li></ul>"
        client.client.chat.completions.create.return_value = response_mock

        result = client.generate_spotify_enhanced_response(
            user_prompt="my top artists",
            system_message="You are a helpful assistant.",
            spotify_data={"artists": [{"name": "Artist 1"}]},
            tool_info={"tool": "get_top_artists", "reasoning": "keyword"},
        )
        assert "<ul>" in result
        assert "```" not in result

    def test_raises_on_api_error(self, client):
        client.client.chat.completions.create.side_effect = Exception("openai down")
        with pytest.raises(Exception, match="OpenAI API error"):
            client.generate_spotify_enhanced_response(
                user_prompt="x",
                system_message="y",
                spotify_data={},
                tool_info={"tool": "get_top_artists", "reasoning": ""},
            )


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
