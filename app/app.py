from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
import json
from dotenv import load_dotenv
from .spotify_mcp import SpotifyMCPTools
from .open_ai_client import OpenAIClient

# Load environment variables from .env file
# This will look for .env in the current directory and parent directories
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "front"  

app = FastAPI(
    title="Prompt Relay API",
    description="POST a prompt, get an OpenAI response.",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---- Schemas ----
class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt to send to OpenAI")
    system: Optional[str] = Field(
        default="You are a concise and helpful assistant with access to Spotify tools. You can help users with their music preferences, top artists, tracks, and playlists.",
        description="Optional system instruction."
    )
    model: Optional[str] = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use."
    )
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    spotify_access_token: Optional[str] = Field(
        default=None,
        description="Spotify access token for authenticated requests"
    )

class AskResponse(BaseModel):
    answer: str

# ---- Initialize clients ----
openai_client = OpenAIClient()
spotify_tools = SpotifyMCPTools()

# ---- Helper functions ----
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

# Spotify intent detection is now handled by openai_client.detect_spotify_intent()

async def execute_spotify_tool(tool_name: str, parameters: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    """Execute Spotify MCP tool"""
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

# Tool detection functions are now handled by openai_client.determine_spotify_tool_with_llm()

# ---- Endpoint ----
@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    try:
        # Check if the prompt requires Spotify functionality
        spotify_intent = openai_client.detect_spotify_intent(body.prompt)
        
        if spotify_intent["requires_spotify"]:
            if not body.spotify_access_token:
                return AskResponse(
                    answer="I can help you with Spotify-related questions, but I need your Spotify access token. Please authenticate with Spotify first by visiting the /login endpoint."
                )
            
            # Use LLM to determine which Spotify tool to use
            available_tools = spotify_tools.get_available_tools()
            tool_info = await openai_client.determine_spotify_tool_with_llm(body.prompt, available_tools)
            
            if tool_info["tool"]:
                # Execute Spotify tool
                spotify_result = await execute_spotify_tool(
                    tool_info["tool"], 
                    tool_info["parameters"], 
                    body.spotify_access_token
                )
                
                if "error" in spotify_result:
                    return AskResponse(answer=f"Spotify error: {spotify_result['error']}")
                
                # Generate response with Spotify data using OpenAI client
                answer = openai_client.generate_spotify_enhanced_response(
                    user_prompt=body.prompt,
                    system_message=body.system,
                    spotify_data=spotify_result,
                    tool_info=tool_info,
                    model=body.model,
                    temperature=body.temperature
                )
                return AskResponse(answer=answer.strip())
            else:
                return AskResponse(
                    answer="I detected you're asking about music, but I couldn't determine the specific Spotify action you want. Try asking about your top artists, top tracks, recently played songs, current playback, or playlists."
                )
        
        # Regular OpenAI response for non-Spotify prompts
        answer = openai_client.generate_response(
            prompt=body.prompt,
            system_message=body.system,
            model=body.model,
            temperature=body.temperature
        )
        return AskResponse(answer=answer.strip())
        
    except Exception as e:
        # Surface a clean 502 to the client while logging the real cause server-side
        raise HTTPException(status_code=502, detail=f"Upstream AI error: {e}")

# ---- Spotify Authentication Endpoints ----
@app.get("/login")
async def spotify_login():
    """Initiate Spotify OAuth flow - redirects directly to Spotify"""
    auth_url = spotify_tools.get_auth_url()
    return RedirectResponse(url=auth_url)

@app.get("/callback")
async def spotify_callback(code: str):
    """Handle Spotify OAuth callback"""
    try:
        token_info = spotify_tools.get_access_token_from_code(code)
        
        # Load success HTML template
        html_content = load_html_template(
            "app/front/success.html",
            "app/front/fallback_success.html",
            {
                "ACCESS_TOKEN": token_info["access_token"],
                "EXPIRES_IN": token_info["expires_in"],
                "REFRESH_TOKEN": token_info.get("refresh_token", "Not provided")
            }
        )
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        # Load error HTML template
        error_html = load_html_template(
            "app/front/error.html",
            "app/front/fallback_error.html",
            {"ERROR_MESSAGE": str(e)}
        )
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=error_html, status_code=400)

@app.get("/")
async def home():
    """Main UI page"""
    html_content = load_html_template(
        "app/front/index.html",
        "app/front/fallback_ui.html"
    )
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

@app.get("/docs-page")
async def docs_page():
    """Documentation page with instructions"""
    html_content = load_html_template(
        "app/front/login_success.html",
        "app/front/fallback_ui.html"
    )
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

@app.get("/spotify/tools", response_class=HTMLResponse)
async def get_spotify_tools(request: Request):
    """Get available Spotify tools"""
    tools = spotify_tools.get_available_tools()  
    return templates.TemplateResponse(
        "list_tools.html",
        {"request": request, "tools": tools}
    )
