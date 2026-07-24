from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float = Field(..., ge=0.0, description="Start time in seconds")
    end: float = Field(..., gt=0.0, description="End time in seconds")
    text: str = Field(..., min_length=1, description="Transcribed text")
    chunk_id: str = Field(..., min_length=1, description="Unique segment identifier")


class TranscriptResult(BaseModel):
    segments: list[TranscriptSegment]
    full_text: str
    language: str