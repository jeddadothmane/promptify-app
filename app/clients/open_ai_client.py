import logging
from openai import OpenAI
import os
import json
from typing import Awaitable, Callable, Dict, Any, Optional, List
from dotenv import load_dotenv
from app.config import OPENAI_MODEL, OPENAI_TEMPERATURE_ROUTING, OPENAI_TEMPERATURE_CREATIVE
from app.utils import deprecated

load_dotenv()

logger = logging.getLogger(__name__)

class OpenAIClient:
    """OpenAI client wrapper with Spotify tool detection and response generation"""

    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    @staticmethod
    def _spotify_tools_to_openai_schema(available_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert spotify_tools.json's param format into OpenAI function-calling tool schemas."""
        schema = []
        for tool in available_tools:
            properties = {}
            required = []
            for param_name, param_info in tool.get("parameters", {}).items():
                properties[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }
                if "default" not in param_info:
                    required.append(param_name)
            schema.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return schema

    async def run_agentic_loop(
        self,
        prompt: str,
        available_tools: List[Dict[str, Any]],
        execute_tool: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        system_message: str,
        model: str = OPENAI_MODEL,
        temperature: float = OPENAI_TEMPERATURE_ROUTING,
        history: Optional[List[Dict[str, str]]] = None,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """Agentic tool-calling loop: the model can call zero, one, or several Spotify
        tools — across multiple turns — before producing its final answer."""
        tools = self._spotify_tools_to_openai_schema(available_tools) if available_tools else None

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_message}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        tool_calls_made: List[Dict[str, Any]] = []

        for iteration in range(max_iterations):
            completion = self.client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=messages,
                tools=tools,
            )
            message = completion.choices[0].message

            if not message.tool_calls:
                return {"answer": (message.content or "").strip(), "tool_calls": tool_calls_made}

            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    parameters = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    parameters = {}

                logger.info("run_agentic_loop | iteration=%d | tool=%s | parameters=%s", iteration, tool_name, parameters)
                result = await execute_tool(tool_name, parameters)
                tool_calls_made.append({"tool": tool_name, "parameters": parameters, "result": result})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

        logger.warning("run_agentic_loop | hit max_iterations=%d, forcing final answer", max_iterations)
        final_completion = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=messages,
        )
        return {
            "answer": (final_completion.choices[0].message.content or "").strip(),
            "tool_calls": tool_calls_made,
        }

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
    
    @deprecated("Replaced by generate_playlist_plan which curates specific tracks instead of genre search strings.")
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
    
    @deprecated("Was the fallback for generate_individual_track_searches, which was replaced by generate_playlist_plan.")
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
    
    @deprecated("Only called by generate_playlist_search_queries, which is itself deprecated.")
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


