from pydantic import BaseModel, Field
from typing import Optional
from app.config import OPENAI_MODEL, OPENAI_TEMPERATURE_CREATIVE


class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: Optional[str] = Field(
        default="You are a concise and helpful assistant with access to Spotify tools. You can help users with their music preferences, top artists, tracks, and playlists."
    )
    model: Optional[str] = Field(default=OPENAI_MODEL)
    temperature: Optional[float] = Field(default=OPENAI_TEMPERATURE_CREATIVE, ge=0.0, le=2.0)
    spotify_access_token: Optional[str] = Field(default=None)
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID. Omit to start a new one.")


class AskResponse(BaseModel):
    answer: str
    conversation_id: Optional[str] = None


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
