from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from .schemas import AskRequest, AskResponse
from dotenv import load_dotenv
from app.clients.spotify_mcp import SpotifyMCPTools
from app.clients.open_ai_client import OpenAIClient
from .utils import load_html_template, execute_spotify_tool
# Load environment variables from .env file
# This will look for .env in the current directory and parent directories
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "view"

app = FastAPI(
    title="Promptify App",
    description="Promptify App",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---- Initialize clients ----
openai_client = OpenAIClient()
spotify_tools = SpotifyMCPTools()

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
            "app/view/success.html",
            "app/view/fallback_success.html",
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
            "app/view/error.html",
            "app/view/fallback_error.html",
            {"ERROR_MESSAGE": str(e)}
        )
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=error_html, status_code=400)

@app.get("/")
async def home():
    """Main UI page"""
    html_content = load_html_template(
        "app/view/index.html",
        "app/view/fallback_ui.html"
    )
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

@app.get("/docs-page")
async def docs_page():
    """Documentation page with instructions"""
    html_content = load_html_template(
        "app/view/login_success.html",
        "app/view/fallback_ui.html"
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
