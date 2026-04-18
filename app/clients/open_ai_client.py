import logging
from openai import OpenAI
import os
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from app.config import OPENAI_MODEL, OPENAI_TEMPERATURE_ROUTING, OPENAI_TEMPERATURE_CREATIVE

load_dotenv()

logger = logging.getLogger(__name__)

class OpenAIClient:
    """OpenAI client wrapper with Spotify tool detection and response generation"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    async def analyze_prompt(self, prompt: str, available_tools: list) -> Dict[str, Any]:
        """Single LLM call: detect Spotify intent and select the right tool + parameters."""

        analysis_prompt = f"""
        You are an AI assistant for a Spotify app. Analyze the user's message and decide two things:
        1. Does this request require Spotify data? (yes/no)
        2. If yes, which tool should be used and with what parameters?

        User message: "{prompt}"

        Available Spotify tools:
        {json.dumps(available_tools, indent=2)}

        Rules:
        - Set "requires_spotify" to true only if the user is asking about music, their Spotify data, playback, playlists, artists, tracks, or wants a playlist created.
        - If "requires_spotify" is false, set "tool" to null and "parameters" to {{}}.
        - Extract any numbers mentioned for limits (e.g. "top 5" → limit=5).
        - For playlist creation requests, always pass the full original prompt as the "prompt" parameter.

        Examples:
        - "What are my top 5 artists?" → requires_spotify=true, tool=get_top_artists, limit=5
        - "What's currently playing?" → requires_spotify=true, tool=get_current_playback
        - "Find songs by Taylor Swift" → requires_spotify=true, tool=search_tracks, query="Taylor Swift"
        - "Create a workout playlist with 20 songs" → requires_spotify=true, tool=create_playlist_from_prompt, prompt="Create a workout playlist with 20 songs"
        - "What is the capital of France?" → requires_spotify=false

        Respond with ONLY a JSON object in this exact format:
        {{
            "requires_spotify": true or false,
            "tool": "tool_name or null",
            "parameters": {{"param1": "value1"}},
            "reasoning": "one sentence explanation"
        }}
        """

        logger.info("analyze_prompt | prompt=%r | model=%s | temperature=%s", prompt, OPENAI_MODEL, OPENAI_TEMPERATURE_ROUTING)
        try:
            completion = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=OPENAI_TEMPERATURE_ROUTING,
                messages=[
                    {"role": "system", "content": "You are a Spotify assistant routing expert. Always respond with valid JSON only."},
                    {"role": "user", "content": analysis_prompt}
                ],
            )

            response_text = completion.choices[0].message.content.strip()

            if response_text.startswith("```"):
                lines = response_text.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = '\n'.join(lines).strip()

            try:
                result = json.loads(response_text)
                parsed = {
                    "requires_spotify": bool(result.get("requires_spotify", False)),
                    "tool": result.get("tool") or None,
                    "parameters": result.get("parameters", {}),
                    "reasoning": result.get("reasoning", "")
                }
                logger.info("analyze_prompt result | requires_spotify=%s | tool=%s | reasoning=%r",
                            parsed["requires_spotify"], parsed["tool"], parsed["reasoning"])
                return parsed
            except json.JSONDecodeError:
                logger.warning("analyze_prompt | LLM returned invalid JSON, falling back to keyword detection")
                return self._fallback_full_analysis(prompt)

        except Exception as e:
            logger.error("analyze_prompt | LLM call failed: %s — falling back to keyword detection", e)
            return self._fallback_full_analysis(prompt)

    def _fallback_full_analysis(self, prompt: str) -> Dict[str, Any]:
        """Fallback when the combined LLM call fails: keyword intent check + keyword tool selection."""
        prompt_lower = prompt.lower()

        spotify_keywords = [
            "top artists", "top tracks", "favorite artists", "favorite songs",
            "recently played", "current song", "what's playing", "playlist",
            "spotify", "music", "song", "artist", "album", "play"
        ]
        requires_spotify = any(kw in prompt_lower for kw in spotify_keywords)

        if not requires_spotify:
            return {"requires_spotify": False, "tool": None, "parameters": {}, "reasoning": "No Spotify keywords found"}

        tool_info = self.fallback_keyword_detection(prompt)
        return {
            "requires_spotify": True,
            "tool": tool_info["tool"],
            "parameters": tool_info["parameters"],
            "reasoning": tool_info["reasoning"]
        }
    
    def fallback_keyword_detection(self, prompt: str) -> Dict[str, Any]:
        """Fallback keyword-based tool detection if LLM fails"""
        import re
        prompt_lower = prompt.lower()
        
        if any(phrase in prompt_lower for phrase in ["top artists", "favorite artists", "most played artists"]):
            numbers = re.findall(r'\d+', prompt)
            limit = int(numbers[0]) if numbers else 5
            return {"tool": "get_top_artists", "parameters": {"limit": limit}, "reasoning": "Keyword detection: top artists"}
        
        elif any(phrase in prompt_lower for phrase in ["top tracks", "favorite songs", "most played songs"]):
            numbers = re.findall(r'\d+', prompt)
            limit = int(numbers[0]) if numbers else 5
            return {"tool": "get_top_tracks", "parameters": {"limit": limit}, "reasoning": "Keyword detection: top tracks"}
        
        elif any(phrase in prompt_lower for phrase in ["recently played", "recent songs", "last played"]):
            numbers = re.findall(r'\d+', prompt)
            limit = int(numbers[0]) if numbers else 20
            return {"tool": "get_recently_played", "parameters": {"limit": limit}, "reasoning": "Keyword detection: recently played"}
        
        elif any(phrase in prompt_lower for phrase in ["current song", "what's playing", "now playing", "current track"]):
            return {"tool": "get_current_playback", "parameters": {}, "reasoning": "Keyword detection: current playback"}
        
        elif any(phrase in prompt_lower for phrase in ["make me a playlist", "create a playlist", "generate a playlist", "build a playlist"]):
            return {"tool": "create_playlist_from_prompt", "parameters": {"prompt": prompt}, "reasoning": "Keyword detection: playlist creation"}
        
        elif any(phrase in prompt_lower for phrase in ["playlist", "playlists"]) and not any(phrase in prompt_lower for phrase in ["make", "create", "generate", "build"]):
            numbers = re.findall(r'\d+', prompt)
            limit = int(numbers[0]) if numbers else 20
            return {"tool": "get_user_playlists", "parameters": {"limit": limit}, "reasoning": "Keyword detection: existing playlists"}
        
        elif "search" in prompt_lower:
            search_query = prompt_lower.replace("search", "").replace("for", "").strip()
            return {"tool": "search_tracks", "parameters": {"query": search_query}, "reasoning": "Keyword detection: search"}
        
        return {"tool": None, "parameters": {}, "reasoning": "No matching tool found"}
    
    def generate_response(self, prompt: str, system_message: str, model: str = OPENAI_MODEL, temperature: float = OPENAI_TEMPERATURE_CREATIVE) -> str:
        """Generate a response using OpenAI"""
        try:
            completion = self.client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def generate_spotify_enhanced_response(self, user_prompt: str, system_message: str, spotify_data: Dict[str, Any],
                                         tool_info: Dict[str, Any], model: str = OPENAI_MODEL, temperature: float = OPENAI_TEMPERATURE_CREATIVE) -> str:
        """Generate a response with Spotify data context"""
        logger.info("generate_spotify_enhanced_response | tool=%s | model=%s | temperature=%s",
                    tool_info.get("tool"), model, temperature)
        enhanced_prompt = f"""
        User asked: "{user_prompt}"
        
        I used the {tool_info["tool"]} tool because: {tool_info.get("reasoning", "No reasoning provided")}
        
        Here's the Spotify data I retrieved:
        {json.dumps(spotify_data, indent=2)}
        
        Please provide a helpful response based on this data, formatting it nicely for the user.
        Please provide a valid format knowing that your response will directly integrated into a HTML file, so please keep in mind that you response is clear to an HTML return like a simple str but in HTML please.
        Please do not return a response containing ```html```
        """
        
        return self.generate_response(enhanced_prompt, system_message, model, temperature)
    
    def generate_playlist_search_queries(self, prompt: str, track_count: int) -> List[str]:
        """Generate optimized search queries for playlist creation using LLM"""
        try:
            search_prompt = f"""
            You are a music search expert. Given a user's playlist request, generate 3-5 optimized search queries for Spotify that will find the best tracks.

            User request: "{prompt}"
            Target track count: {track_count}

            Guidelines:
            1. Extract key musical elements (genres, moods, artists, decades, instruments)
            2. Create diverse search queries that will find different types of tracks
            3. Use specific terms that Spotify's search will understand well
            4. Include both broad and specific queries
            5. Avoid overly generic terms like "music" or "songs"

            Examples:
            - "Make me a workout playlist" → ["workout music", "gym playlist", "high energy", "motivational music", "fitness tracks"]
            - "Chill study music" → ["chill study", "ambient study", "lo-fi", "acoustic study", "instrumental study"]
            - "Melodic death metal" → ["melodic death metal", "death metal", "melodic metal", "extreme metal", "blackened death"]

            Respond with ONLY a JSON array of search queries:
            ["query1", "query2", "query3", "query4", "query5"]
            """
            
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,  # Lower temperature for more consistent results
                messages=[
                    {"role": "system", "content": "You are a music search expert. Generate optimized Spotify search queries based on user requests. Always respond with valid JSON only."},
                    {"role": "user", "content": search_prompt}
                ],
            )
            
            response_text = completion.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                # Remove opening ```json or ``` and closing ```
                lines = response_text.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]  # Remove first line
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]  # Remove last line
                response_text = '\n'.join(lines).strip()
            
            # Parse the JSON response
            try:
                queries = json.loads(response_text)
                if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                    return queries[:5]  # Limit to 5 queries max
                else:
                    raise ValueError("Invalid format")
            except (json.JSONDecodeError, ValueError):
                # Fallback to basic keyword extraction
                return self._fallback_search_queries(prompt)
                
        except Exception as e:
            print(f"LLM search query generation failed: {e}")
            return self._fallback_search_queries(prompt)
    
    def _fallback_individual_searches(self, prompt: str, track_count: int) -> List[str]:
        """Fallback method to generate individual search queries when LLM fails"""
        import re
        
        # Extract key terms
        keywords = prompt.lower().split()
        stop_words = ['make', 'me', 'a', 'playlist', 'of', 'tracks', 'songs', 'with', 'combining', 'and', 'or', 'the', 'for', 'create', 'generate', 'build']
        search_terms = [word for word in keywords if word not in stop_words]
        
        # Create base query
        base_query = ' '.join(search_terms[:3]) if search_terms else prompt[:30]
        
        # Generate variations for individual tracks
        queries = []
        variations = [
            f"{base_query}",
            f"{base_query} popular",
            f"{base_query} classic",
            f"{base_query} modern",
            f"{base_query} best",
            f"{base_query} hits",
            f"{base_query} essential",
            f"{base_query} top",
            f"{base_query} famous"
        ]
        
        # Add genre-specific variations
        genre_terms = ['metal', 'rock', 'pop', 'electronic', 'jazz', 'classical', 'hip hop', 'country', 'blues', 'folk', 'reggae', 'punk']
        for term in search_terms:
            if any(genre in term for genre in genre_terms):
                variations.extend([
                    f"{term}",
                    f"{term} music",
                    f"{term} songs",
                    f"{term} tracks"
                ])
        
        # Return unique queries up to track_count
        unique_queries = []
        for query in variations:
            if query not in unique_queries and len(unique_queries) < track_count:
                unique_queries.append(query)
        
        # Fill remaining slots if needed
        while len(unique_queries) < track_count:
            unique_queries.append(f"{base_query} {len(unique_queries) + 1}")
        
        return unique_queries[:track_count]
    
    def _fallback_search_queries(self, prompt: str) -> List[str]:
        """Fallback method to generate search queries when LLM fails"""
        import re
        
        # Extract key terms
        keywords = prompt.lower().split()
        stop_words = ['make', 'me', 'a', 'playlist', 'of', 'tracks', 'songs', 'with', 'combining', 'and', 'or', 'the', 'for', 'create', 'generate', 'build']
        search_terms = [word for word in keywords if word not in stop_words]
        
        # Create basic queries
        queries = []
        if search_terms:
            queries.append(' '.join(search_terms[:3]))  # First 3 terms
            queries.append(' '.join(search_terms[:2]))  # First 2 terms
            if len(search_terms) > 1:
                queries.append(search_terms[0])  # First term only
        
        # Add genre-specific queries if detected
        genre_terms = ['metal', 'rock', 'pop', 'electronic', 'jazz', 'classical', 'hip hop', 'country', 'blues', 'folk', 'reggae', 'punk']
        for term in search_terms:
            if any(genre in term for genre in genre_terms):
                queries.append(term)
        
        return queries[:5] if queries else [prompt[:50]]

    def generate_playlist_plan(self, prompt: str, track_count: int) -> Dict[str, Any]:
        """Ask the LLM to curate a full playlist plan: name, description, and specific tracks."""
        plan_prompt = f"""
        You are an expert music curator. The user wants a playlist based on this request: "{prompt}"

        Your job is to recommend {track_count} real, specific songs that perfectly match the request.

        Guidelines:
        - Pick real songs by real artists that actually exist on Spotify.
        - Ensure variety: different artists, moods, tempos, and sub-styles within the theme.
        - Come up with a creative, fitting playlist name (not generic like "My Playlist").
        - Write a short, evocative playlist description (1-2 sentences).

        Respond with ONLY a JSON object in this exact format:
        {{
            "name": "playlist name",
            "description": "playlist description",
            "tracks": [
                {{"title": "Song Title", "artist": "Artist Name"}},
                ...
            ]
        }}

        The "tracks" array must contain exactly {track_count} entries.
        """

        logger.info("generate_playlist_plan | prompt=%r | track_count=%d | model=%s | temperature=%s",
                    prompt, track_count, OPENAI_MODEL, OPENAI_TEMPERATURE_CREATIVE)
        try:
            completion = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=OPENAI_TEMPERATURE_CREATIVE,
                messages=[
                    {"role": "system", "content": "You are an expert music curator. Always respond with valid JSON only."},
                    {"role": "user", "content": plan_prompt}
                ],
            )

            response_text = completion.choices[0].message.content.strip()

            if response_text.startswith("```"):
                lines = response_text.split('\n')
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = '\n'.join(lines).strip()

            result = json.loads(response_text)

            if not isinstance(result.get("tracks"), list):
                raise ValueError("Missing tracks list")

            plan = {
                "name": result.get("name", "Promptify Playlist"),
                "description": result.get("description", "Created by Promptify, your AI Spotify assistant."),
                "tracks": result["tracks"][:track_count]
            }
            logger.info("generate_playlist_plan | name=%r | tracks_planned=%d", plan["name"], len(plan["tracks"]))
            return plan

        except Exception as e:
            logger.error("generate_playlist_plan | LLM call failed: %s", e)
            return {
                "name": "Promptify Playlist",
                "description": "Created by Promptify, your AI Spotify assistant.",
                "tracks": []
            }


