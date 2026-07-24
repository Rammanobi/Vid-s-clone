from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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


@dataclass
class AccountData:
    instagram_id: str
    username: str
    follower_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_competitor: bool = False


@dataclass
class ReelData:
    account_id: str
    instagram_reel_id: str
    video_url: str
    caption: str | None = None
    duration_sec: float = 0.0
    posted_at: datetime | None = None
    transcript: str | None = None
    transcript_json: list[dict[str, Any]] | None = None
    visual_topics: list[str] = field(default_factory=list)
    text_overlays: list[str] = field(default_factory=list)
    visual_summary: str | None = None


@dataclass
class ReelMetricData:
    reel_id: str
    views: int = 0
    likes: int = 0
    comments_count: int = 0
    saves: int | None = None
    shares: int | None = None
    reach: int | None = None
    engagement_rate: float = 0.0
    save_rate: float | None = None
    share_rate: float | None = None
    comment_rate: float | None = None
    virality_score: float = 1.0
    view_to_follower: float = 0.0
    metric_quality: MetricQuality = MetricQuality.FULL
    is_volatile: bool = False


@dataclass
class CommentData:
    reel_id: str
    author_id: str
    text: str
    is_creator: bool = False
    posted_at: datetime | None = None


@dataclass
class AccountSnapshotData:
    account_id: str
    follower_count: int
    snapshot_at: datetime | None = None