from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiker_ingestion.models import (
    AccountData,
    AccountSnapshotData,
    CommentData,
    MetricQuality,
    ReelData,
    ReelMetricData,
)
from hiker_ingestion.logging_setup import get_logger

logger = get_logger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_int_optional(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_str(value: Any, default: str | None = None) -> str | None:
    if value is None:
        return default
    return str(value)


def _safe_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


def map_account(api_response: dict[str, Any]) -> AccountData:
    return AccountData(
        instagram_id=str(api_response.get("pk", api_response.get("id", ""))),
        username=api_response.get("username", ""),
        follower_count=_safe_int(
            api_response.get("follower_count", api_response.get("followerCount", 0))
        ),
        following_count=_safe_int(
            api_response.get("following_count", api_response.get("followingCount", 0))
        ),
        posts_count=_safe_int(
            api_response.get("media_count", api_response.get("postsCount", 0))
        ),
        is_competitor=False,
    )


def map_reel(
    api_response: dict[str, Any], account_id: str
) -> ReelData:
    media_id = str(
        api_response.get("pk", api_response.get("id", api_response.get("media_id", "")))
    )
    caption = (
        api_response.get("caption_text")
        or (api_response.get("caption", {}) or {}).get("text")
        or None
    )

    return ReelData(
        account_id=account_id,
        instagram_reel_id=media_id,
        video_url=_safe_str(
            api_response.get("video_url", api_response.get("permalink", "")), ""
        ),
        caption=caption,
        duration_sec=_safe_float(
            api_response.get("video_duration", api_response.get("durationSec", 0.0))
        ),
        posted_at=_safe_timestamp(
            api_response.get("taken_at", api_response.get("postedAt"))
        ),
    )


def map_comment(
    api_response: dict[str, Any],
    reel_id: str,
    creator_id: str | None = None,
) -> CommentData:
    author_pk = str(
        api_response.get(
            "pk",
            api_response.get("user_id", api_response.get("authorId", "")),
        )
    )

    return CommentData(
        reel_id=reel_id,
        author_id=_safe_str(author_pk, ""),
        text=_safe_str(
            api_response.get("text", api_response.get("content", "")), ""
        ),
        is_creator=(author_pk == creator_id) if creator_id else False,
        posted_at=_safe_timestamp(
            api_response.get("created_at", api_response.get("postedAt"))
        ),
    )


def map_metric(
    api_response: dict[str, Any],
    reel_id: str,
    follower_count: int | None = None,
) -> ReelMetricData:
    views = _safe_int(api_response.get("view_count", api_response.get("play_count", 0)))
    likes = _safe_int(api_response.get("like_count", 0))
    comments_count = _safe_int(api_response.get("comment_count", 0))
    saves = _safe_int_optional(
        api_response.get("save_count")
    )
    shares = _safe_int_optional(
        api_response.get("share_count")
    )
    reach = _safe_int_optional(
        api_response.get("reach_count")
    )

    engagement_rate: float = 0.0
    if follower_count and follower_count > 0:
        engagement_rate = round(
            ((likes + comments_count + (saves or 0) + (shares or 0)) / follower_count)
            * 100,
            4,
        )

    save_rate: float | None = None
    if views > 0 and saves is not None:
        save_rate = round(saves / views * 100, 4)

    share_rate: float | None = None
    if views > 0 and shares is not None:
        share_rate = round(shares / views * 100, 4)

    comment_rate: float | None = None
    if views > 0:
        comment_rate = round(comments_count / views * 100, 4)

    virality_score = round(
        (engagement_rate + (share_rate or 0) * 2) / 10 + 1.0, 4
    )

    view_to_follower: float = 0.0
    if follower_count and follower_count > 0:
        view_to_follower = round(views / follower_count, 4)

    is_partial = any(
        x is None for x in [saves, shares, reach]
    )

    return ReelMetricData(
        reel_id=reel_id,
        views=views,
        likes=likes,
        comments_count=comments_count,
        saves=saves,
        shares=shares,
        reach=reach,
        engagement_rate=engagement_rate,
        save_rate=save_rate,
        share_rate=share_rate,
        comment_rate=comment_rate,
        virality_score=virality_score,
        view_to_follower=view_to_follower,
        metric_quality=MetricQuality.PARTIAL if is_partial else MetricQuality.FULL,
    )


def map_account_snapshot(
    account_data: AccountData,
) -> AccountSnapshotData:
    return AccountSnapshotData(
        account_id=account_data.instagram_id,
        follower_count=account_data.follower_count,
    )