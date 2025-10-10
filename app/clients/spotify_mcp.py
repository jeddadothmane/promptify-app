from typing import Dict, Any, List, Optional
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class SpotifyMCPTools:
    """Spotify MCP Tools for interacting with Spotify API"""
    
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
        self.scope = "user-top-read user-read-recently-played user-read-playback-state user-modify-playback-state playlist-read-private playlist-modify-public playlist-modify-private"
        
        self.sp_oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope
        )
        
        self.sp = None
        self.access_token = None
    
    def authenticate(self, access_token: str = None):
        """Authenticate with Spotify using access token"""
        if access_token:
            self.access_token = access_token
            self.sp = Spotify(auth=access_token)
            return True
        return False
    
    def get_auth_url(self) -> str:
        """Get Spotify authorization URL"""
        return self.sp_oauth.get_authorize_url()
    
    def get_access_token_from_code(self, code: str) -> Dict[str, Any]:
        """Get access token from authorization code"""
        return self.sp_oauth.get_access_token(code)
    
    async def get_top_artists(self, limit: int = 5, time_range: str = "medium_term") -> Dict[str, Any]:
        """Get user's top artists"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            results = self.sp.current_user_top_artists(limit=limit, time_range=time_range)
            artists = []
            for artist in results['items']:
                artists.append({
                    "name": artist['name'],
                    "popularity": artist['popularity'],
                    "genres": artist['genres'],
                    "followers": artist['followers']['total'],
                    "external_urls": artist['external_urls']
                })
            return {"top_artists": artists}
        except Exception as e:
            return {"error": f"Failed to get top artists: {str(e)}"}
    
    async def get_top_tracks(self, limit: int = 5, time_range: str = "medium_term") -> Dict[str, Any]:
        """Get user's top tracks"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            results = self.sp.current_user_top_tracks(limit=limit, time_range=time_range)
            tracks = []
            for track in results['items']:
                tracks.append({
                    "name": track['name'],
                    "artists": [artist['name'] for artist in track['artists']],
                    "album": track['album']['name'],
                    "popularity": track['popularity'],
                    "duration_ms": track['duration_ms'],
                    "external_urls": track['external_urls']
                })
            return {"top_tracks": tracks}
        except Exception as e:
            return {"error": f"Failed to get top tracks: {str(e)}"}
    
    async def get_recently_played(self, limit: int = 20) -> Dict[str, Any]:
        """Get user's recently played tracks"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            results = self.sp.current_user_recently_played(limit=limit)
            tracks = []
            for item in results['items']:
                track = item['track']
                tracks.append({
                    "name": track['name'],
                    "artists": [artist['name'] for artist in track['artists']],
                    "album": track['album']['name'],
                    "played_at": item['played_at'],
                    "external_urls": track['external_urls']
                })
            return {"recently_played": tracks}
        except Exception as e:
            return {"error": f"Failed to get recently played: {str(e)}"}
    
    async def get_current_playback(self) -> Dict[str, Any]:
        """Get current playback state"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            playback = self.sp.current_playback()
            if playback:
                return {
                    "is_playing": playback['is_playing'],
                    "track": {
                        "name": playback['item']['name'],
                        "artists": [artist['name'] for artist in playback['item']['artists']],
                        "album": playback['item']['album']['name'],
                        "duration_ms": playback['item']['duration_ms'],
                        "progress_ms": playback['progress_ms']
                    },
                    "device": playback['device']['name'] if playback['device'] else None
                }
            else:
                return {"message": "No active playback"}
        except Exception as e:
            return {"error": f"Failed to get current playback: {str(e)}"}
    
    async def search_tracks(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for tracks"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            results = self.sp.search(q=query, type='track', limit=limit)
            tracks = []
            for track in results['tracks']['items']:
                tracks.append({
                    "name": track['name'],
                    "artists": [artist['name'] for artist in track['artists']],
                    "album": track['album']['name'],
                    "popularity": track['popularity'],
                    "external_urls": track['external_urls']
                })
            return {"search_results": tracks}
        except Exception as e:
            return {"error": f"Failed to search tracks: {str(e)}"}
    
    async def get_user_playlists(self, limit: int = 20) -> Dict[str, Any]:
        """Get user's playlists"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            playlists = self.sp.current_user_playlists(limit=limit)
            playlist_list = []
            for playlist in playlists['items']:
                playlist_list.append({
                    "name": playlist['name'],
                    "description": playlist['description'],
                    "tracks": playlist['tracks']['total'],
                    "public": playlist['public'],
                    "external_urls": playlist['external_urls']
                })
            return {"playlists": playlist_list}
        except Exception as e:
            return {"error": f"Failed to get playlists: {str(e)}"}
    
    async def create_playlist_from_prompt(self, prompt: str, playlist_name: str = None, description: str = None, public: bool = True) -> Dict[str, Any]:
        """Create a playlist based on user prompt using LLM-generated individual track searches"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            # Import OpenAI client for generating search queries
            from .open_ai_client import OpenAIClient
            openai_client = OpenAIClient()
            
            # Generate playlist name if not provided
            if not playlist_name:
                playlist_name = f"AI Generated Playlist - {prompt[:50]}..."
            
            # Generate description if not provided
            if not description:
                description = "This Playlist was created by Promptify, your personal AI spotify assistant."
            
            # Extract number if mentioned in prompt
            import re
            numbers = re.findall(r'\d+', prompt)
            track_limit = int(numbers[0]) if numbers else 15
            
            # Use LLM to generate individual search queries for each track
            individual_queries = openai_client.generate_individual_track_searches(prompt, track_limit)
            
            # Create the playlist first
            user_id = self.sp.current_user()['id']
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=playlist_name,
                public=public,
                description=description
            )
            
            # Search for individual tracks using LLM-generated queries
            track_uris = []
            track_details = []
            successful_searches = []
            
            for i, query in enumerate(individual_queries):
                try:
                    # Search for 1-3 tracks with this specific query
                    search_results = self.sp.search(q=query, type='track', limit=3)
                    
                    if search_results['tracks']['items']:
                        # Take the first (best) result from this search
                        best_track = search_results['tracks']['items'][0]
                        
                        # Check if we already have this track (avoid duplicates)
                        if best_track['uri'] not in track_uris:
                            track_uris.append(best_track['uri'])
                            track_details.append({
                                "name": best_track['name'],
                                "artist": best_track['artists'][0]['name'],
                                "album": best_track['album']['name'],
                                "uri": best_track['uri'],
                                "search_query": query
                            })
                            successful_searches.append({
                                "query": query,
                                "track_found": f"{best_track['name']} by {best_track['artists'][0]['name']}"
                            })
                        
                        # If we have enough tracks, break
                        if len(track_uris) >= track_limit:
                            break
                    
                except Exception as e:
                    print(f"Search failed for query '{query}': {e}")
                    continue
            
            # If we still don't have enough tracks, try fallback searches
            if len(track_uris) < track_limit:
                remaining_needed = track_limit - len(track_uris)
                keywords = prompt.lower().split()
                stop_words = ['make', 'me', 'a', 'playlist', 'of', 'tracks', 'songs', 'with', 'combining', 'and', 'or', 'the', 'for', 'create', 'generate', 'build']
                search_terms = [word for word in keywords if word not in stop_words]
                
                if search_terms:
                    fallback_query = ' '.join(search_terms[:3])
                    try:
                        fallback_results = self.sp.search(q=fallback_query, type='track', limit=remaining_needed * 2)
                        for track in fallback_results['tracks']['items']:
                            if track['uri'] not in track_uris and len(track_uris) < track_limit:
                                track_uris.append(track['uri'])
                                track_details.append({
                                    "name": track['name'],
                                    "artist": track['artists'][0]['name'],
                                    "album": track['album']['name'],
                                    "uri": track['uri'],
                                    "search_query": f"fallback: {fallback_query}"
                                })
                                successful_searches.append({
                                    "query": f"fallback: {fallback_query}",
                                    "track_found": f"{track['name']} by {track['artists'][0]['name']}"
                                })
                    except Exception as e:
                        print(f"Fallback search failed: {e}")
            
            # Add tracks to playlist
            if track_uris:
                self.sp.user_playlist_add_tracks(
                    user=user_id,
                    playlist_id=playlist['id'],
                    tracks=track_uris[:track_limit]
                )
            
            return {
                "playlist": {
                    "id": playlist['id'],
                    "name": playlist['name'],
                    "description": playlist['description'],
                    "public": playlist['public'],
                    "tracks_added": len(track_uris[:track_limit]),
                    "external_urls": playlist['external_urls']
                },
                "track_details": track_details,
                "search_results": successful_searches,
                "tracks_found": len(track_uris),
                "individual_search_method": True,
                "llm_enhanced": True
            }
            
        except Exception as e:
            return {"error": f"Failed to create playlist: {str(e)}"}
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available Spotify tools"""
        return [
            {
                "name": "get_top_artists",
                "description": "Get user's top artists",
                "parameters": {
                    "limit": {"type": "integer", "default": 5, "description": "Number of artists to return"},
                    "time_range": {"type": "string", "default": "medium_term", "description": "Time range: short_term, medium_term, long_term"}
                }
            },
            {
                "name": "get_top_tracks",
                "description": "Get user's top tracks",
                "parameters": {
                    "limit": {"type": "integer", "default": 5, "description": "Number of tracks to return"},
                    "time_range": {"type": "string", "default": "medium_term", "description": "Time range: short_term, medium_term, long_term"}
                }
            },
            {
                "name": "get_recently_played",
                "description": "Get user's recently played tracks",
                "parameters": {
                    "limit": {"type": "integer", "default": 20, "description": "Number of tracks to return"}
                }
            },
            {
                "name": "get_current_playback",
                "description": "Get current playback state",
                "parameters": {}
            },
            {
                "name": "search_tracks",
                "description": "Search for tracks",
                "parameters": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10, "description": "Number of results to return"}
                }
            },
            {
                "name": "get_user_playlists",
                "description": "Get user's playlists",
                "parameters": {
                    "limit": {"type": "integer", "default": 20, "description": "Number of playlists to return"}
                }
            },
            {
                "name": "create_playlist_from_prompt",
                "description": "Create a playlist based on user prompt with AI-selected tracks",
                "parameters": {
                    "prompt": {"type": "string", "description": "User prompt describing the playlist to create"},
                    "playlist_name": {"type": "string", "default": None, "description": "Custom name for the playlist"},
                    "description": {"type": "string", "default": None, "description": "Custom description for the playlist"},
                    "public": {"type": "boolean", "default": True, "description": "Whether the playlist should be public"}
                }
            }
        ]
