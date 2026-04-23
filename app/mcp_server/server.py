import os
import logging
from mcp.server.fastmcp import FastMCP
from spotipy import Spotify

logger = logging.getLogger(__name__)

mcp = FastMCP("spotify-tools")

_token = os.environ.get("SPOTIFY_ACCESS_TOKEN", "")
sp = Spotify(auth=_token) if _token else None


@mcp.tool()
async def get_top_artists(limit: int = 5, time_range: str = "medium_term") -> dict:
    """Get user's top artists from Spotify"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}
    logger.info("get_top_artists | limit=%d | time_range=%s", limit, time_range)
    try:
        results = sp.current_user_top_artists(limit=limit, time_range=time_range)
        artists = []
        for artist in results["items"]:
            artists.append({
                "name": artist["name"],
                "popularity": artist["popularity"],
                "genres": artist["genres"],
                "followers": artist["followers"]["total"],
                "external_urls": artist["external_urls"],
            })
        logger.info("get_top_artists | returned %d artists", len(artists))
        return {"top_artists": artists}
    except Exception as e:
        logger.error("get_top_artists | failed: %s", e)
        return {"error": f"Failed to get top artists: {str(e)}"}


@mcp.tool()
async def get_top_tracks(limit: int = 5, time_range: str = "medium_term") -> dict:
    """Get user's top tracks from Spotify"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}
    logger.info("get_top_tracks | limit=%d | time_range=%s", limit, time_range)
    try:
        results = sp.current_user_top_tracks(limit=limit, time_range=time_range)
        tracks = []
        for track in results["items"]:
            tracks.append({
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": track["album"]["name"],
                "popularity": track["popularity"],
                "duration_ms": track["duration_ms"],
                "external_urls": track["external_urls"],
            })
        logger.info("get_top_tracks | returned %d tracks", len(tracks))
        return {"top_tracks": tracks}
    except Exception as e:
        logger.error("get_top_tracks | failed: %s", e)
        return {"error": f"Failed to get top tracks: {str(e)}"}


@mcp.tool()
async def get_recently_played(limit: int = 20) -> dict:
    """Get user's recently played tracks from Spotify"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}
    logger.info("get_recently_played | limit=%d", limit)
    try:
        results = sp.current_user_recently_played(limit=limit)
        tracks = []
        for item in results["items"]:
            track = item["track"]
            tracks.append({
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": track["album"]["name"],
                "played_at": item["played_at"],
                "external_urls": track["external_urls"],
            })
        logger.info("get_recently_played | returned %d tracks", len(tracks))
        return {"recently_played": tracks}
    except Exception as e:
        logger.error("get_recently_played | failed: %s", e)
        return {"error": f"Failed to get recently played: {str(e)}"}


@mcp.tool()
async def get_current_playback() -> dict:
    """Get the user's current Spotify playback state"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}
    logger.info("get_current_playback | fetching playback state")
    try:
        playback = sp.current_playback()
        if playback:
            track_name = playback["item"]["name"]
            logger.info("get_current_playback | is_playing=%s | track=%r", playback["is_playing"], track_name)
            return {
                "is_playing": playback["is_playing"],
                "track": {
                    "name": track_name,
                    "artists": [artist["name"] for artist in playback["item"]["artists"]],
                    "album": playback["item"]["album"]["name"],
                    "duration_ms": playback["item"]["duration_ms"],
                    "progress_ms": playback["progress_ms"],
                },
                "device": playback["device"]["name"] if playback["device"] else None,
            }
        logger.info("get_current_playback | no active playback")
        return {"message": "No active playback"}
    except Exception as e:
        logger.error("get_current_playback | failed: %s", e)
        return {"error": f"Failed to get current playback: {str(e)}"}


@mcp.tool()
async def search_tracks(query: str, limit: int = 10) -> dict:
    """Search for tracks on Spotify"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}
    logger.info("search_tracks | query=%r | limit=%d", query, limit)
    try:
        results = sp.search(q=query, type="track", limit=limit)
        tracks = []
        for track in results["tracks"]["items"]:
            tracks.append({
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": track["album"]["name"],
                "popularity": track["popularity"],
                "external_urls": track["external_urls"],
            })
        logger.info("search_tracks | returned %d results for query=%r", len(tracks), query)
        return {"search_results": tracks}
    except Exception as e:
        logger.error("search_tracks | failed: %s", e)
        return {"error": f"Failed to search tracks: {str(e)}"}


@mcp.tool()
async def get_user_playlists(limit: int = 20) -> dict:
    """Get the user's Spotify playlists"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}
    logger.info("get_user_playlists | limit=%d", limit)
    try:
        playlists = sp.current_user_playlists(limit=limit)
        playlist_list = []
        for playlist in playlists["items"]:
            playlist_list.append({
                "name": playlist["name"],
                "description": playlist["description"],
                "tracks": playlist["tracks"]["total"],
                "public": playlist["public"],
                "external_urls": playlist["external_urls"],
            })
        logger.info("get_user_playlists | returned %d playlists", len(playlist_list))
        return {"playlists": playlist_list}
    except Exception as e:
        logger.error("get_user_playlists | failed: %s", e)
        return {"error": f"Failed to get playlists: {str(e)}"}


@mcp.tool()
async def create_playlist_from_prompt(
    prompt: str,
    playlist_name: str = "",
    description: str = "",
    public: bool = True,
) -> dict:
    """Create a Spotify playlist based on a natural-language prompt using LLM-curated tracks"""
    if not sp:
        return {"error": "Not authenticated with Spotify"}

    logger.info("create_playlist_from_prompt | prompt=%r", prompt)
    try:
        import re
        from app.clients.open_ai_client import OpenAIClient

        openai_client = OpenAIClient()

        numbers = re.findall(r"\d+", prompt)
        track_limit = int(numbers[0]) if numbers else 15
        logger.info("create_playlist_from_prompt | track_limit=%d", track_limit)

        plan = openai_client.generate_playlist_plan(prompt, track_limit)
        logger.info("create_playlist_from_prompt | plan ready | name=%r | tracks_planned=%d",
                    plan["name"], len(plan["tracks"]))

        final_name = playlist_name or plan["name"]
        final_description = description or plan["description"]

        user_id = sp.current_user()["id"]
        playlist = sp.user_playlist_create(
            user=user_id,
            name=final_name,
            public=public,
            description=final_description,
        )
        logger.info("create_playlist_from_prompt | playlist created | id=%s | name=%r",
                    playlist["id"], playlist["name"])

        track_uris = []
        track_details = []

        for track_suggestion in plan["tracks"]:
            if len(track_uris) >= track_limit:
                break

            title = track_suggestion.get("title", "")
            artist = track_suggestion.get("artist", "")
            query = f"track:{title} artist:{artist}"

            try:
                results = sp.search(q=query, type="track", limit=3)
                items = results["tracks"]["items"]

                if not items:
                    logger.debug("create_playlist_from_prompt | loosening search | title=%r artist=%r", title, artist)
                    results = sp.search(q=f"{title} {artist}", type="track", limit=3)
                    items = results["tracks"]["items"]

                if items:
                    best = items[0]
                    if best["uri"] not in track_uris:
                        track_uris.append(best["uri"])
                        track_details.append({
                            "intended": f"{title} by {artist}",
                            "found": f"{best['name']} by {best['artists'][0]['name']}",
                            "album": best["album"]["name"],
                            "uri": best["uri"],
                        })
                        logger.info("create_playlist_from_prompt | track matched | intended=%r | found=%r",
                                    f"{title} by {artist}", f"{best['name']} by {best['artists'][0]['name']}")
                else:
                    logger.warning("create_playlist_from_prompt | no match | title=%r | artist=%r", title, artist)

            except Exception as e:
                logger.error("create_playlist_from_prompt | search error | title=%r | artist=%r | error=%s", title, artist, e)
                continue

        if track_uris:
            sp.user_playlist_add_tracks(user=user_id, playlist_id=playlist["id"], tracks=track_uris)
            logger.info("create_playlist_from_prompt | done | tracks_added=%d / %d requested",
                        len(track_uris), track_limit)

        return {
            "playlist": {
                "id": playlist["id"],
                "name": playlist["name"],
                "description": playlist["description"],
                "public": playlist["public"],
                "tracks_added": len(track_uris),
                "external_urls": playlist["external_urls"],
            },
            "track_details": track_details,
            "tracks_requested": track_limit,
            "tracks_found": len(track_uris),
        }

    except Exception as e:
        logger.exception("create_playlist_from_prompt | unhandled error: %s", e)
        return {"error": f"Failed to create playlist: {str(e)}"}


if __name__ == "__main__":
    mcp.run()
