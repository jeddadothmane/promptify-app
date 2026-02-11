from openai import OpenAI
import os
import json
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class OpenAIClient:
    """OpenAI client wrapper with Spotify tool detection and response generation"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    def detect_spotify_intent(self, prompt: str) -> Dict[str, Any]:
        """Detect if the prompt requires Spotify functionality"""
        prompt_lower = prompt.lower()
        
        # Keywords that indicate Spotify functionality
        spotify_keywords = [
            "top artists", "top tracks", "favorite artists", "favorite songs",
            "recently played", "current song", "what's playing", "playlist",
            "spotify", "music", "song", "artist", "album", "play"
        ]
        
        # Check for Spotify-related keywords
        for keyword in spotify_keywords:
            if keyword in prompt_lower:
                return {"requires_spotify": True, "intent": keyword}
        
        return {"requires_spotify": False}
    
    async def determine_spotify_tool_with_llm(self, prompt: str, available_tools: list) -> Dict[str, Any]:
        """Use LLM to intelligently determine which Spotify tool to use based on user intent"""
        
        # Create a detailed prompt for the LLM to analyze user intent
        tool_analysis_prompt = f"""
        Analyze the user's request and determine which Spotify tool to use. The user said: "{prompt}"

        Available Spotify tools:
        {json.dumps(available_tools, indent=2)}

        Based on the user's request, determine:
        1. Which tool to use (or "none" if no tool matches)
        2. What parameters to pass to the tool
        3. Extract any numbers mentioned (for limits)

        Examples:
        - "What are my top 5 artists?" → get_top_artists with limit=5
        - "Show me my favorite songs" → get_top_tracks with limit=5
        - "What's currently playing?" → get_current_playback
        - "What did I listen to recently?" → get_recently_played
        - "Find songs by Taylor Swift" → search_tracks with query="Taylor Swift"
        - "What playlists do I have?" → get_user_playlists
        - "Make me a playlist of 15 tracks combining melodic death/black metal" → create_playlist_from_prompt with prompt="Make me a playlist of 15 tracks combining melodic death/black metal"
        - "Create a workout playlist with 20 songs" → create_playlist_from_prompt with prompt="Create a workout playlist with 20 songs"
        - "Generate a chill playlist for studying" → create_playlist_from_prompt with prompt="Generate a chill playlist for studying"

        Respond with ONLY a JSON object in this exact format:
        {{
            "tool": "tool_name_or_none",
            "parameters": {{"param1": "value1", "param2": "value2"}},
            "reasoning": "brief explanation of why this tool was chosen"
        }}
        """
        
        try:
            # Use OpenAI to analyze the user's intent
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,  # Low temperature for consistent tool selection
                messages=[
                    {"role": "system", "content": "You are a tool selection expert. Analyze user requests and determine the appropriate Spotify tool to use. Always respond with valid JSON only."},
                    {"role": "user", "content": tool_analysis_prompt}
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
                result = json.loads(response_text)
                return {
                    "tool": result.get("tool"),
                    "parameters": result.get("parameters", {}),
                    "reasoning": result.get("reasoning", "")
                }
            except json.JSONDecodeError:
                # Fallback to keyword detection if LLM response is invalid
                return self.fallback_keyword_detection(prompt)
                
        except Exception as e:
            # Fallback to keyword detection if LLM call fails
            print(f"LLM tool detection failed: {e}")
            return self.fallback_keyword_detection(prompt)
    
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
    
    def generate_response(self, prompt: str, system_message: str, model: str = "gpt-4o-mini", temperature: float = 0.7) -> str:
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
                                         tool_info: Dict[str, Any], model: str = "gpt-4o-mini", temperature: float = 0.7) -> str:
        """Generate a response with Spotify data context"""
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

    def generate_individual_track_searches(self, prompt: str, track_count: int) -> List[str]:
        """Generate individual search queries for each track in the playlist using LLM"""
        try:
            search_prompt = f"""
            You are a music curator expert. Given a user's playlist request, generate {track_count} specific search queries - one for each track that should be in the playlist.

            User request: "{prompt}"
            Number of tracks needed: {track_count}

            Guidelines:
            1. Create {track_count} diverse, specific search queries
            2. Each query should target a different aspect/style within the requested genre/mood
            3. Include variety in artists, sub-genres, moods, and styles
            4. Make each query specific enough to find 1-3 good tracks
            5. Avoid duplicate queries
            6. Use terms that Spotify's search will understand well

            Examples for "Make me a workout playlist with 5 tracks":
            ["high energy workout", "motivational gym music", "intense cardio tracks", "power workout songs", "energetic fitness music"]

            Examples for "Melodic death metal playlist with 3 tracks":
            ["melodic death metal classics", "modern melodic death", "melodic blackened death"]

            Examples for "Chill study music with 4 tracks":
            ["ambient study music", "lo-fi hip hop", "acoustic instrumental", "soft electronic"]

            Respond with ONLY a JSON array of exactly {track_count} search queries:
            ["query1", "query2", "query3", ...]
            """
            
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,  # Slightly higher for more variety
                messages=[
                    {"role": "system", "content": "You are a music curator expert. Generate specific search queries for individual tracks. Always respond with valid JSON only."},
                    {"role": "user", "content": search_prompt}
                ],
            )
            
            response_text = completion.choices[0].message.content.strip()
            print(response_text)
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
                    return queries[:track_count]  # Ensure we get exactly the requested number
                else:
                    raise ValueError("Invalid format")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"JSON parsing error in generate_individual_track_searches: {e}")
                print(f"Response text: {response_text}")
                import traceback
                traceback.print_exc()
                # Fallback to basic keyword extraction
                return self._fallback_individual_searches(prompt, track_count)
                
        except Exception as e:
            print(f"LLM individual track search generation failed: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_individual_searches(prompt, track_count)


