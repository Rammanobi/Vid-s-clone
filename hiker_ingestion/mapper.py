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

# Virality score weights (design.md Decision 6 / reel-metrics spec 6.6) -
# named constants so they can be recalibrated later without touching the formula.
VIRALITY_ENGAGEMENT_WEIGHT = 0.5
VIRALITY_SHARE_WEIGHT = 0.3
VIRALITY_VIEW_TO_FOLLOWER_WEIGHT = 0.2


def _coerce_id(value: Any) -> str:
    """Render any ID-like field (pk/id/user_id) as str. NEVER int()/float() -
    under safe_int=true a 19-digit media pk arrives as a JSON string and an
    11-digit user pk arrives as a JSON number; both must round-trip exactly."""
    if value is None:
        return ""
    return str(value)


def unwrap_user(response: dict[str, Any]) -> dict[str, Any]:
    """/v2/user/by/username -> the `user` object (flat, no further nesting)."""
    return response.get("user") or {}


def unwrap_clips(response: dict[str, Any]) -> list[dict[str, Any]]:
    """/v2/user/clips -> response.items[].media (double-nested: each array
    element is {"media": {...}}, not the media object itself)."""
    items = ((response.get("response") or {}).get("items")) or []
    return [item.get("media") or {} for item in items if item]


def unwrap_comments(response: dict[str, Any]) -> list[dict[str, Any]]:
    """/v2/media/comments -> response.comments[] (flat elements)."""
    return ((response.get("response") or {}).get("comments")) or []


def unwrap_media_info(response: dict[str, Any]) -> dict[str, Any]:
    """/v2/media/info/by/code -> the `media_or_ad` object."""
    return response.get("media_or_ad") or {}


def unwrap_insight(response: dict[str, Any]) -> dict[str, Any]:
    """/v1/media/insight -> payload sits at the response root, no wrapper."""
    return response


def is_reel(media: dict[str, Any]) -> bool:
    """A media item is a Reel iff product_type == "clips" and media_type == 2."""
    return media.get("product_type") == "clips" and media.get("media_type") == 2


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
        # ponytail: strip tzinfo even if already a datetime - every timestamp
        # column in the schema is `timestamp without time zone` (Prisma's
        # postgres default for DateTime), and asyncpg rejects a tz-aware
        # value against a naive column with an unencodable-datetime error.
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, (int, float)):
        # taken_at/created_at are Unix seconds in UTC (verified against real
        # payloads). Compute via UTC, then drop tzinfo to match the naive
        # column - the value is still correctly UTC, just unlabeled.
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
    return None


def map_account(user: dict[str, Any]) -> AccountData:
    """Reads from the UNWRAPPED user object (see unwrap_user). Passing the
    raw envelope here is the bug that left instagramId empty and aborted
    ingestion."""
    return AccountData(
        instagram_id=_coerce_id(user.get("pk", user.get("id"))),
        username=_safe_str(user.get("username"), "") or "",
        follower_count=_safe_int(user.get("follower_count"), 0),
        following_count=_safe_int(user.get("following_count"), 0),
        posts_count=_safe_int(user.get("media_count"), 0),
        is_competitor=False,
        full_name=_safe_str(user.get("full_name")),
        biography=_safe_str(user.get("biography")),
        profile_pic_url=_safe_str(user.get("profile_pic_url")),
        is_verified=bool(user.get("is_verified", False)),
        is_private=bool(user.get("is_private", False)),
        external_url=_safe_str(user.get("external_url")),
    )


def map_reel(
    media: dict[str, Any], account_id: str
) -> ReelData:
    """Reads from the UNWRAPPED media object (see unwrap_clips/unwrap_media_info)."""
    video_versions = media.get("video_versions") or []
    video_url = ""
    if video_versions:
        # design Decision 4: pick highest bandwidth, not blind index-0.
        best = max(video_versions, key=lambda v: v.get("bandwidth") or 0)
        video_url = _safe_str(best.get("url"), "") or ""

    caption_obj = media.get("caption")
    caption = caption_obj.get("text") if isinstance(caption_obj, dict) else None

    return ReelData(
        account_id=account_id,
        instagram_reel_id=_coerce_id(media.get("pk")),
        video_url=video_url,
        caption=caption or None,
        duration_sec=_safe_float(media.get("video_duration"), 0.0),
        posted_at=_safe_timestamp(media.get("taken_at")),
    )


def map_comment(
    api_response: dict[str, Any],
    reel_id: str,
    creator_id: str | None = None,
) -> CommentData:
    # The comment's own `pk` is the COMMENT id, not the author. The author is
    # `user.pk` (mirrored at top-level `user_id`). Verified on the raw payload:
    # comment pk=18209380177352304 vs user.pk=47831239820.
    author_pk = _coerce_id(
        (api_response.get("user") or {}).get("pk")
        or api_response.get("user_id")
    )

    # ponytail: derived by comparison, not by reading `is_created_by_media_owner`
    # — that field is absent (not False) on all 32 sampled top-level comments.
    is_creator = bool(creator_id) and author_pk == _coerce_id(creator_id)

    return CommentData(
        reel_id=reel_id,
        author_id=author_pk,
        text=_safe_str(
            api_response.get("text", api_response.get("content", "")), ""
        ),
        is_creator=is_creator,
        posted_at=_safe_timestamp(
            api_response.get("created_at", api_response.get("postedAt"))
        ),
    )


def map_metric(
    api_response: dict[str, Any],
    reel_id: str,
    follower_count: int | None = None,
) -> ReelMetricData:
    # 6.1: views <- play_count. `view_count` does not exist in any payload.
    raw_views = api_response.get("play_count")
    raw_likes = api_response.get("like_count")
    raw_comments = api_response.get("comment_count")
    saves = _safe_int_optional(api_response.get("save_count"))
    # 6.2: shares <- reshare_count. NOT share_count (absent), NOT
    # media_repost_count (a different, much smaller metric).
    shares = _safe_int_optional(api_response.get("reshare_count"))

    views = _safe_int(raw_views, 0)
    likes = _safe_int(raw_likes, 0)
    comments_count = _safe_int(raw_comments, 0)
    followers = _safe_int(follower_count, 0)

    # 6.5: engagementRate divides by views (plays), matching save_rate/
    # share_rate/comment_rate below - not follower_count.
    engagement_rate: float = 0.0
    if views > 0:
        engagement_rate = round(
            (likes + comments_count + (saves or 0) + (shares or 0)) / views * 100,
            4,
        )

    save_rate: float = 0.0
    if views > 0 and saves is not None:
        save_rate = round(saves / views * 100, 4)

    share_rate: float = 0.0
    if views > 0 and shares is not None:
        share_rate = round(shares / views * 100, 4)

    comment_rate: float = 0.0
    if views > 0:
        comment_rate = round(comments_count / views * 100, 4)

    view_to_follower: float = 0.0
    if followers > 0:
        view_to_follower = round(views / followers * 100, 4)

    # 6.6: named weight constants, not inlined literals.
    virality_score = round(
        engagement_rate * VIRALITY_ENGAGEMENT_WEIGHT
        + share_rate * VIRALITY_SHARE_WEIGHT
        + view_to_follower * VIRALITY_VIEW_TO_FOLLOWER_WEIGHT,
        4,
    )

    # 6.7: FULL requires views/likes/commentsCount/saves/shares ALL non-null.
    # reach/impressions are excluded entirely - they no longer exist here.
    is_full = all(
        x is not None for x in (raw_views, raw_likes, raw_comments, saves, shares)
    )

    return ReelMetricData(
        reel_id=reel_id,
        views=views,
        likes=likes,
        comments_count=comments_count,
        saves=saves,
        shares=shares,
        engagement_rate=engagement_rate,
        save_rate=save_rate,
        share_rate=share_rate,
        comment_rate=comment_rate,
        virality_score=virality_score,
        view_to_follower=view_to_follower,
        metric_quality=MetricQuality.FULL if is_full else MetricQuality.PARTIAL,
    )


def map_account_snapshot(
    account_data: AccountData,
) -> AccountSnapshotData:
    return AccountSnapshotData(
        account_id=account_data.instagram_id,
        follower_count=account_data.follower_count,
    )


if __name__ == "__main__":
    # ponytail: quick sanity check against documented real values - not a
    # substitute for the full pytest suite, just a fast "did I break the
    # obvious contract" gate for this module.
    sample_media = {
        "pk": "3944679501543145356",
        "code": "Da-URtaPn-M",
        "product_type": "clips",
        "media_type": 2,
        "video_versions": [
            {"bandwidth": 500000, "url": "https://example.com/low.mp4"},
            {"bandwidth": 1284735, "url": "https://example.com/high.mp4"},
        ],
        "caption": {"text": "Comment \"certificate\" and I'll send you the official links.\n"},
        "video_duration": 39.75,
        "taken_at": 1784462647,
        "play_count": 11875,
        "like_count": 146,
        "comment_count": 122,
        "save_count": 136,
        "reshare_count": 74,
    }

    assert is_reel(sample_media) is True

    reel = map_reel(sample_media, account_id="acct-1")
    assert reel.instagram_reel_id == "3944679501543145356"
    assert reel.video_url == "https://example.com/high.mp4"  # highest bandwidth wins
    assert reel.caption == "Comment \"certificate\" and I'll send you the official links.\n"
    assert reel.duration_sec == 39.75
    assert reel.posted_at == datetime.fromtimestamp(1784462647, tz=timezone.utc).replace(tzinfo=None)

    metric = map_metric(sample_media, reel_id="reel-1", follower_count=150165)
    assert metric.views == 11875
    assert metric.saves == 136
    assert metric.shares == 74
    assert metric.metric_quality == MetricQuality.FULL
    assert metric.engagement_rate == round((146 + 122 + 136 + 74) / 11875 * 100, 4) == 4.0253
    assert metric.save_rate == round(136 / 11875 * 100, 4) == 1.1453
    assert metric.share_rate == round(74 / 11875 * 100, 4) == 0.6232
    assert metric.view_to_follower == round(11875 / 150165 * 100, 4) == 7.9080
    assert metric.virality_score == round(4.0253 * 0.5 + 0.6232 * 0.3 + 7.9080 * 0.2, 4) == 3.7812

    # zero-guard: views=0 and followers=0 must never raise.
    zero_media = dict(sample_media)
    zero_media["play_count"] = 0
    zero_metric = map_metric(zero_media, reel_id="reel-2", follower_count=0)
    assert zero_metric.views == 0
    assert zero_metric.engagement_rate == 0.0
    assert zero_metric.save_rate == 0.0
    assert zero_metric.share_rate == 0.0
    assert zero_metric.comment_rate == 0.0
    assert zero_metric.view_to_follower == 0.0
    assert zero_metric.virality_score == 0.0

    # instagramId coercion tolerates both numeric and string pk under safe_int.
    assert _coerce_id(45093317380) == "45093317380"
    assert _coerce_id("3944679501543145356") == "3944679501543145356"

    account = map_account({"pk": 45093317380, "username": "okaashish",
                            "follower_count": 150165, "following_count": 389,
                            "media_count": 533})
    assert account.instagram_id == "45093317380"
    assert account.username == "okaashish"

    print("mapper self-check: all assertions passed")