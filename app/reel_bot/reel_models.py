from __future__ import annotations

from pydantic import BaseModel, Field


class ReelIngestPayload(BaseModel):
    instagram_handle: str = Field(..., description="Public Instagram handle")


class ReelIngestResponse(BaseModel):
    instagram_handle: str
    reels_synced: int
    avg_wpm: float | None = None
    top_keywords: list[str] = Field(default_factory=list)


class ReelChatMessage(BaseModel):
    role: str
    content: str


class ReelChatRequest(BaseModel):
    instagram_handle: str = Field(..., description="Public Instagram handle")
    session_id: str | None = Field(None, description="Existing session ID, or None to create new")
    message: str = Field(..., description="User message")


class ReelChatResponse(BaseModel):
    session_id: str
    response: str


class StoredReel(BaseModel):
    instagram_handle: str
    instagram_reel_id: str
    video_url: str
    caption: str | None = None
    views: int = 0
    likes: int = 0
    comments_count: int = 0
    shares: int = 0
    duration_sec: float | None = None
    posted_at: str | None = None
    raw_transcript: str | None = None
    clean_transcript: str | None = None
    word_count: int | None = None
    wpm: float | None = None
    top_keywords: list[str] = Field(default_factory=list)
