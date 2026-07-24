from __future__ import annotations

from pydantic import BaseModel, Field


class FrameEmbedding(BaseModel):
    frame_index: int
    embedding: list[float] = Field(..., min_length=1536, max_length=1536)


class VisualTopicResult(BaseModel):
    topics: list[str]
    visual_summary: str
    combined_embedding: list[float] = Field(..., min_length=1536, max_length=1536)