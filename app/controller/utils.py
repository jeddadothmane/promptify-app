from typing import Dict, Any

from app.clients.spotify_mcp import SpotifyMCPTools


def load_html_template(template_path: str, fallback_path: str = None, replacements: dict = None) -> str:
    """Load HTML template with fallback and replacements"""
    try:
        with open(template_path, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError:
        if fallback_path:
            try:
                with open(fallback_path, "r", encoding="utf-8") as file:
                    content = file.read()
            except FileNotFoundError:
                content = "<h1>Template not found</h1>"
        else:
            content = "<h1>Template not found</h1>"

    # Apply replacements if provided
    if replacements:
        for key, value in replacements.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))

    return content


async def execute_spotify_tool(tool_name: str, parameters: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    """Execute Spotify MCP tool"""
    spotify_tools = SpotifyMCPTools()

    if not spotify_tools.authenticate(access_token):
        return {"error": "Failed to authenticate with Spotify"}

    try:
        if tool_name == "get_top_artists":
            return await spotify_tools.get_top_artists(
                limit=parameters.get("limit", 5),
                time_range=parameters.get("time_range", "medium_term")
            )
        elif tool_name == "get_top_tracks":
            return await spotify_tools.get_top_tracks(
                limit=parameters.get("limit", 5),
                time_range=parameters.get("time_range", "medium_term")
            )
        elif tool_name == "get_recently_played":
            return await spotify_tools.get_recently_played(
                limit=parameters.get("limit", 20)
            )
        elif tool_name == "get_current_playback":
            return await spotify_tools.get_current_playback()
        elif tool_name == "search_tracks":
            return await spotify_tools.search_tracks(
                query=parameters.get("query", ""),
                limit=parameters.get("limit", 10)
            )
        elif tool_name == "get_user_playlists":
            return await spotify_tools.get_user_playlists(
                limit=parameters.get("limit", 20)
            )
        elif tool_name == "create_playlist_from_prompt":
            return await spotify_tools.create_playlist_from_prompt(
                prompt=parameters.get("prompt", ""),
                playlist_name=parameters.get("playlist_name", None),
                description=parameters.get("description", None),
                public=parameters.get("public", True)
            )
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}

