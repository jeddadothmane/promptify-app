from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

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
