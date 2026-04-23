import logging
from pathlib import Path
from typing import Dict, Any, List
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import os
import json

logger = logging.getLogger(__name__)


class SpotifyClient:
    """Handles Spotify OAuth flow and exposes tool definitions for LLM tool selection.
    Actual tool execution is handled by the MCP server (app/mcp_server/server.py)."""

    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
        self.scope = "user-top-read user-read-recently-played user-read-playback-state user-modify-playback-state playlist-read-private playlist-modify-public playlist-modify-private"
        self.data_file = Path(__file__).resolve().parent / "resources" / "spotify_tools.json"

        self.sp_oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
        )

        self.sp = None
        self.access_token = None

    def authenticate(self, access_token: str = None):
        """Authenticate with Spotify using an access token"""
        if access_token:
            self.access_token = access_token
            self.sp = Spotify(auth=access_token)
            return True
        return False

    def get_auth_url(self) -> str:
        """Get Spotify authorization URL"""
        return self.sp_oauth.get_authorize_url()

    def get_access_token_from_code(self, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for an access token"""
        return self.sp_oauth.get_access_token(code)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Load tool definitions from JSON (used to inform OpenAI which tools exist)"""
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                tools = json.load(f)
                if not isinstance(tools, list):
                    raise ValueError("spotify_tools.json must contain a list of tools")
                return tools
        except FileNotFoundError:
            logger.warning("get_available_tools | JSON file not found: %s", self.data_file)
            return []
        except json.JSONDecodeError as e:
            logger.error("get_available_tools | invalid JSON in %s: %s", self.data_file, e)
            return []
