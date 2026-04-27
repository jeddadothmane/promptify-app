import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


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

    if replacements:
        for key, value in replacements.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))

    return content


async def execute_spotify_tool(tool_name: str, parameters: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    """Execute a Spotify tool via the MCP server subprocess"""
    project_root = Path(__file__).resolve().parents[2]
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server.server"],
        env={
            "SPOTIFY_ACCESS_TOKEN": access_token,
            "SPOTIFY_CLIENT_ID": os.environ.get("SPOTIFY_CLIENT_ID", ""),
            "SPOTIFY_CLIENT_SECRET": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
            "SPOTIFY_REDIRECT_URI": os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "PATH": os.environ.get("PATH", ""),
        },
        cwd=str(project_root),
    )
    try:
        # Strip None values so MCP uses each tool's declared parameter defaults
        clean_params = {k: v for k, v in parameters.items() if v is not None}

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=clean_params)

        if result.isError:
            error_text = result.content[0].text if result.content and hasattr(result.content[0], "text") else "unknown error"
            logger.error("execute_spotify_tool | tool=%s | MCP error: %s", tool_name, error_text)
            return {"error": error_text}
        if result.content and hasattr(result.content[0], "text"):
            return json.loads(result.content[0].text)
        return {"error": "Empty tool result"}

    except Exception as e:
        logger.error("execute_spotify_tool | MCP call failed | tool=%s | error=%s", tool_name, e)
        return {"error": f"Tool execution failed: {str(e)}"}
