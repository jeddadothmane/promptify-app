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
from app.clients.spotify_oauth import SpotifyClient
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
spotify_tools = SpotifyClient()


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

        # ── Agentic tool-calling ────────────────────────────────────
        # The model decides itself whether Spotify data is needed, which tool(s)
        # to call, and can chain multiple tool calls before answering.
        available_tools = spotify_tools.get_available_tools() if body.spotify_access_token else []

        async def execute_tool(tool_name: str, parameters: dict) -> dict:
            logger.info("Executing Spotify tool | tool=%s | parameters=%s", tool_name, parameters)
            return await execute_spotify_tool(tool_name, parameters, body.spotify_access_token)

        system_message = body.system
        if not body.spotify_access_token:
            system_message += (
                "\n\nNo Spotify access token is available right now, so you cannot call any Spotify tools. "
                "If the user's request needs live Spotify data, tell them to authenticate by visiting /login."
            )
        system_message += (
            "\n\nYour response will be rendered directly in an HTML page — "
            "return valid HTML only, no markdown code fences."
        )

        result = await openai_client.run_agentic_loop(
            prompt=body.prompt,
            available_tools=available_tools,
            execute_tool=execute_tool,
            system_message=system_message,
            model=body.model,
            temperature=body.temperature,
            history=history,
        )
        answer = result["answer"]
        logger.info("Response generated successfully | tool_calls=%d",
                    len(result["tool_calls"]))

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
