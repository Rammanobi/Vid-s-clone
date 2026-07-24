from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class HookType(str, Enum):
    CURIOSITY = "CURIOSITY"
    CONTRARIAN = "CONTRARIAN"
    STORY = "STORY"
    PROBLEM_SOLUTION = "PROBLEM_SOLUTION"
    QUESTION = "QUESTION"
    OTHER = "OTHER"


class ContentFormat(str, Enum):
    TUTORIAL = "TUTORIAL"
    BEHIND_THE_SCENES = "BEHIND_THE_SCENES"
    TALKING_HEAD = "TALKING_HEAD"
    SCREEN_RECORDING = "SCREEN_RECORDING"
    SKIT = "SKIT"
    OTHER = "OTHER"


class MetricQuality(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class ReelUpdateSchema(BaseModel):
    transcript: str | None = Field(None, max_length=100000)
    transcript_json: list[dict[str, Any]] | None = None
    text_overlays: list[str] = Field(default_factory=list)
    visual_topics: list[str] = Field(default_factory=list)
    visual_summary: str | None = Field(None, max_length=5000)
    combined_embedding: list[float] | None = Field(
        None, min_length=1536, max_length=1536
    )

    @field_validator("transcript_json")
    @classmethod
    def validate_transcript_segments(
        cls, v: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        if v is None:
            return None
        for i, seg in enumerate(v):
            if not isinstance(seg, dict):
                raise ValueError(f"segment {i} must be a dict")
            if "start" not in seg or "end" not in seg or "text" not in seg:
                raise ValueError(
                    f"segment {i} missing required fields (start, end, text)"
                )
            if not isinstance(seg["start"], (int, float)):
                raise ValueError(f"segment {i}.start must be numeric")
            if not isinstance(seg["end"], (int, float)):
                raise ValueError(f"segment {i}.end must be numeric")
            if seg["start"] < 0:
                raise ValueError(f"segment {i}.start must be >= 0")
            if seg["end"] <= seg["start"]:
                raise ValueError(f"segment {i}.end must be > start")
            if not isinstance(seg.get("text"), str) or not seg["text"].strip():
                raise ValueError(f"segment {i}.text must be non-empty string")
            if "chunk_id" not in seg or not isinstance(seg["chunk_id"], str):
                raise ValueError(f"segment {i} missing chunk_id")
        return v


class ContentIntelligenceSchema(BaseModel):
    reel_id: str
    topic: str | None = Field(None, max_length=500)
    hook_type: HookType | None = None
    hook_text: str | None = Field(None, max_length=1000)
    cta: str | None = Field(None, max_length=1000)
    content_format: ContentFormat | None = None
    teaching_style: str | None = Field(None, max_length=200)
    narrative_style: str | None = Field(None, max_length=200)
    audience_intent: str | None = Field(None, max_length=200)
    sentiment: str | None = Field(None, max_length=100)
    visual_style: str | None = Field(None, max_length=200)


class ReelMetricSchema(BaseModel):
    reel_id: str
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments_count: int = Field(default=0, ge=0)
    saves: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    engagement_rate: float = Field(default=0.0, ge=0.0)
    save_rate: float | None = Field(default=None, ge=0.0)
    share_rate: float | None = Field(default=None, ge=0.0)
    comment_rate: float | None = Field(default=None, ge=0.0)
    virality_score: float = Field(default=1.0, ge=0.0)
    view_to_follower: float = Field(default=0.0, ge=0.0)
    metric_quality: MetricQuality = MetricQuality.FULL
    is_volatile: bool = False