import logging
import logging.config
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from spotipy import Spotify
from .schemas import AskRequest, AskResponse, ConversationOut, MessageOut
from dotenv import load_dotenv
from app.clients.spotify_mcp import SpotifyMCPTools
from app.clients.open_ai_client import OpenAIClient
from app.database import init_db
from app import repositories
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
TEMPLATES_DIR = BASE_DIR / "view" / "html"

app = FastAPI(title="Promptify App", description="Promptify App", version="1.0.0")
app.mount("/view", StaticFiles(directory=str(BASE_DIR / "view")), name="view")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---- Initialize clients ----
openai_client = OpenAIClient()
spotify_tools = SpotifyMCPTools()


@app.on_event("startup")
async def startup():
    init_db()


def _get_user_id(access_token: str) -> str | None:
    try:
        return Spotify(auth=access_token).current_user()["id"]
    except Exception:
        return None

# ---- Chat endpoint ----
@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    logger.info("POST /ask | prompt=%r | model=%s | has_token=%s | conversation=%s",
                body.prompt, body.model, bool(body.spotify_access_token), body.conversation_id)
    try:
        # ── Resolve user identity & conversation ──────────────────
        user_id = _get_user_id(body.spotify_access_token) if body.spotify_access_token else None
        conversation_id = body.conversation_id

        if user_id and not conversation_id:
            title = " ".join(body.prompt.split()[:6])
            conversation_id = repositories.create_conversation(user_id, title)
            logger.info("New conversation created | id=%s", conversation_id)

        # ── Load history ──────────────────────────────────────────
        history = []
        if conversation_id:
            raw = repositories.get_messages(conversation_id)
            history = [{"role": m["role"], "content": m["content"]} for m in raw]
            logger.info("Loaded %d history messages | conversation=%s", len(history), conversation_id)

        # ── Prompt analysis ───────────────────────────────────────
        available_tools = spotify_tools.get_available_tools()
        analysis = await openai_client.analyze_prompt(body.prompt, available_tools)
        logger.info("Prompt analysis | requires_spotify=%s | tool=%s | reasoning=%r",
                    analysis["requires_spotify"], analysis["tool"], analysis["reasoning"])

        if not analysis["requires_spotify"]:
            logger.info("No Spotify intent detected — returning guidance message")
            return AskResponse(
                answer="I'm here to help you with your Spotify requests. Try asking about your top artists, recent tracks, playlists, or ask me to create one for you!",
                conversation_id=conversation_id
            )

        if not body.spotify_access_token:
            logger.warning("Spotify intent detected but no access token provided")
            return AskResponse(
                answer="I can help you with Spotify-related questions, but I need your Spotify access token. Please authenticate with Spotify first by visiting the /login endpoint.",
                conversation_id=conversation_id
            )

        if not analysis["tool"]:
            logger.warning("Spotify intent detected but no tool could be resolved | prompt=%r", body.prompt)
            return AskResponse(
                answer="I detected you're asking about music, but I couldn't determine the specific Spotify action you want. Try asking about your top artists, top tracks, recently played songs, current playback, or playlists.",
                conversation_id=conversation_id
            )

        logger.info("Executing Spotify tool | tool=%s | parameters=%s", analysis["tool"], analysis["parameters"])
        spotify_result = await execute_spotify_tool(
            analysis["tool"],
            analysis["parameters"],
            body.spotify_access_token
        )

        if "error" in spotify_result:
            logger.error("Spotify tool error | tool=%s | error=%s", analysis["tool"], spotify_result["error"])
            return AskResponse(answer=f"Spotify error: {spotify_result['error']}", conversation_id=conversation_id)

        logger.info("Spotify tool succeeded | tool=%s | generating response", analysis["tool"])
        answer = openai_client.generate_spotify_enhanced_response(
            user_prompt=body.prompt,
            system_message=body.system,
            spotify_data=spotify_result,
            tool_info=analysis,
            model=body.model,
            temperature=body.temperature,
            history=history,
        )
        answer = answer.strip()
        logger.info("Response generated successfully | tool=%s", analysis["tool"])

        # ── Persist messages ──────────────────────────────────────
        if conversation_id and user_id:
            repositories.save_message(conversation_id, "user", body.prompt)
            repositories.save_message(conversation_id, "assistant", answer)
            repositories.set_conversation_title(conversation_id, " ".join(body.prompt.split()[:6]))

        return AskResponse(answer=answer, conversation_id=conversation_id)

    except Exception as e:
        logger.exception("Unhandled error in /ask | prompt=%r", body.prompt)
        raise HTTPException(status_code=502, detail=f"Upstream AI error: {e}")


# ---- Conversation endpoints ----
@app.get("/conversations/{user_id}", response_model=List[ConversationOut])
async def list_conversations(user_id: str):
    return repositories.get_conversations(user_id)


@app.get("/conversations/{conversation_id}/messages", response_model=List[MessageOut])
async def get_conversation_messages(conversation_id: str):
    conv = repositories.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return repositories.get_messages(conversation_id)


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str):
    repositories.delete_conversation(conversation_id, user_id)
    return {"deleted": conversation_id}

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

        user_id = _get_user_id(token_info["access_token"]) or ""
        html_content = load_html_template(
            "app/view/html/success.html",
            "app/view/html/fallback_success.html",
            {
                "ACCESS_TOKEN": token_info["access_token"],
                "EXPIRES_IN": token_info["expires_in"],
                "REFRESH_TOKEN": token_info.get("refresh_token", "Not provided"),
                "USER_ID": user_id,
            }
        )

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error("OAuth callback failed | error=%s", e)
        error_html = load_html_template(
            "app/view/html/error.html",
            "app/view/html/fallback_error.html",
            {"ERROR_MESSAGE": str(e)}
        )

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=error_html, status_code=400)

@app.get("/")
async def home():
    """Main UI page"""
    html_content = load_html_template(
        "app/view/html/index.html",
        "app/view/html/fallback_ui.html"
    )
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

@app.get("/docs-page")
async def docs_page():
    """Documentation page with instructions"""
    html_content = load_html_template(
        "app/view/html/login_success.html",
        "app/view/html/fallback_ui.html"
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
