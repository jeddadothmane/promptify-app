"""Integration tests for Spotify OAuth endpoints."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture()
def tc(in_memory_db):
    with (
        patch("app.controller.app.OpenAIClient"),
        patch("app.controller.app.SpotifyClient") as MockSpotify,
        patch("app.database.init_db"),
    ):
        MockSpotify.return_value.get_auth_url.return_value = "https://accounts.spotify.com/authorize?test=1"
        MockSpotify.return_value.get_access_token_from_code.return_value = {
            "access_token": "fake_access_token",
            "expires_in": 3600,
            "refresh_token": "fake_refresh",
        }
        MockSpotify.return_value.get_available_tools.return_value = []

        from fastapi.testclient import TestClient
        from app.controller.app import app
        with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as c:
            yield c


class TestLoginEndpoint:
    def test_redirects_to_spotify(self, tc):
        resp = tc.get("/login")
        assert resp.status_code in (302, 307)
        assert "spotify.com" in resp.headers["location"]


class TestCallbackEndpoint:
    def test_successful_callback_returns_html(self, tc):
        with patch("app.controller.app._get_user_id", return_value="spotify_user_123"):
            resp = tc.get("/callback?code=auth_code_123", follow_redirects=True)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_failed_callback_returns_400(self, tc):
        with (
            patch("app.controller.app.spotify_tools") as mock_st,
            patch("app.controller.app._get_user_id", return_value=None),
        ):
            mock_st.get_access_token_from_code.side_effect = Exception("invalid code")
            resp = tc.get("/callback?code=bad_code", follow_redirects=True)
        assert resp.status_code == 400
