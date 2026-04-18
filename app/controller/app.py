import logging
import logging.config
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from .schemas import AskRequest, AskResponse
from dotenv import load_dotenv
from app.clients.spotify_mcp import SpotifyMCPTools
from app.clients.open_ai_client import OpenAIClient
from .utils import load_html_template, execute_spotify_tool

load_dotenv()

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
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
    logger.info("POST /ask | prompt=%r | model=%s | has_token=%s",
                body.prompt, body.model, bool(body.spotify_access_token))
    try:
        available_tools = spotify_tools.get_available_tools()
        analysis = await openai_client.analyze_prompt(body.prompt, available_tools)

        logger.info("Prompt analysis | requires_spotify=%s | tool=%s | reasoning=%r",
                    analysis["requires_spotify"], analysis["tool"], analysis["reasoning"])

        if not analysis["requires_spotify"]:
            logger.info("No Spotify intent detected — returning guidance message")
            return AskResponse(
                answer="I'm here to help you with your Spotify requests. Try asking about your top artists, recent tracks, playlists, or ask me to create one for you!"
            )

        if not body.spotify_access_token:
            logger.warning("Spotify intent detected but no access token provided")
            return AskResponse(
                answer="I can help you with Spotify-related questions, but I need your Spotify access token. Please authenticate with Spotify first by visiting the /login endpoint."
            )

        if not analysis["tool"]:
            logger.warning("Spotify intent detected but no tool could be resolved | prompt=%r", body.prompt)
            return AskResponse(
                answer="I detected you're asking about music, but I couldn't determine the specific Spotify action you want. Try asking about your top artists, top tracks, recently played songs, current playback, or playlists."
            )

        logger.info("Executing Spotify tool | tool=%s | parameters=%s", analysis["tool"], analysis["parameters"])
        spotify_result = await execute_spotify_tool(
            analysis["tool"],
            analysis["parameters"],
            body.spotify_access_token
        )

        if "error" in spotify_result:
            logger.error("Spotify tool error | tool=%s | error=%s", analysis["tool"], spotify_result["error"])
            return AskResponse(answer=f"Spotify error: {spotify_result['error']}")

        logger.info("Spotify tool succeeded | tool=%s | generating response", analysis["tool"])
        answer = openai_client.generate_spotify_enhanced_response(
            user_prompt=body.prompt,
            system_message=body.system,
            spotify_data=spotify_result,
            tool_info=analysis,
            model=body.model,
            temperature=body.temperature
        )
        logger.info("Response generated successfully | tool=%s", analysis["tool"])
        return AskResponse(answer=answer.strip())

    except Exception as e:
        logger.exception("Unhandled error in /ask | prompt=%r", body.prompt)
        raise HTTPException(status_code=502, detail=f"Upstream AI error: {e}")

# ---- Spotify Authentication Endpoints ----
@app.get("/login")
async def spotify_login():
    logger.info("GET /login | initiating Spotify OAuth flow")
    auth_url = spotify_tools.get_auth_url()
    return RedirectResponse(url=auth_url)

@app.get("/callback")
async def spotify_callback(code: str):
    logger.info("GET /callback | received OAuth code")
    try:
        token_info = spotify_tools.get_access_token_from_code(code)
        logger.info("OAuth callback succeeded | expires_in=%s", token_info.get("expires_in"))

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
        logger.error("OAuth callback failed | error=%s", e)
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
