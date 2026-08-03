from __future__ import annotations

from dataclasses import dataclass

from app.logging_setup import get_logger

logger = get_logger(__name__)

FOLLOWER_VOLATILITY_THRESHOLD = 100

# Must match hiker_ingestion/mapper.py's VIRALITY_* constants and
# openspec/changes/fix-hiker-ingestion/specs/reel-metrics/spec.md exactly —
# this is the same formula computed via a second code path.
VIRALITY_ENGAGEMENT_WEIGHT = 0.5
VIRALITY_SHARE_WEIGHT = 0.3
VIRALITY_VIEW_TO_FOLLOWER_WEIGHT = 0.2


@dataclass
class ReelMetricsResult:
    reel_id: str
    views: int = 0
    likes: int = 0
    comments_count: int = 0
    saves: int | None = None
    shares: int | None = None
    engagement_rate: float = 0.0
    save_rate: float | None = None
    share_rate: float | None = None
    comment_rate: float | None = None
    virality_score: float = 1.0
    view_to_follower: float = 0.0
    growth_rate: float | None = None
    posting_frequency: float | None = None
    avg_watch_time_sec: float | None = None
    content_consistency: float | None = None
    audience_growth: int | None = None
    metric_quality: str = "FULL"
    is_volatile: bool = False
    follower_count: int | None = None
    prev_follower_count: int | None = None


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator <= 0:
        return default
    return numerator / denominator


def compute_engagement_rate(
    likes: int,
    comments: int,
    saves: int | None,
    shares: int | None,
    views: int,
) -> tuple[float, str]:
    if views <= 0:
        return 0.0, "FULL"
    total = likes + comments + (saves or 0) + (shares or 0)
    rate = (total / views) * 100.0
    quality = "PARTIAL" if saves is None or shares is None else "FULL"
    return round(rate, 4), quality


def compute_save_rate(saves: int | None, views: int) -> tuple[float | None, str]:
    if saves is None:
        return None, "PARTIAL"
    if views <= 0:
        return 0.0, "FULL"
    rate = (saves / views) * 100.0
    return round(rate, 4), "FULL"


def compute_share_rate(shares: int | None, views: int) -> tuple[float | None, str]:
    if shares is None:
        return None, "PARTIAL"
    if views <= 0:
        return 0.0, "FULL"
    rate = (shares / views) * 100.0
    return round(rate, 4), "FULL"


def compute_comment_rate(comments: int, views: int, comments_disabled: bool = False) -> tuple[float, str]:
    if comments_disabled:
        return 0.0, "FULL"
    if views <= 0:
        return 0.0, "FULL"
    rate = (comments / views) * 100.0
    return round(rate, 4), "FULL"


def compute_virality_score(
    engagement_rate: float,
    share_rate: float | None,
    view_to_follower: float,
) -> float:
    # ponytail: reuses the three already-zero-guarded rates rather than
    # re-deriving from raw counts, so this can't diverge from them and can't
    # raise ZeroDivisionError itself. Matches
    # hiker_ingestion/mapper.py::map_metric's viralityScore exactly.
    return round(
        engagement_rate * VIRALITY_ENGAGEMENT_WEIGHT
        + (share_rate or 0.0) * VIRALITY_SHARE_WEIGHT
        + view_to_follower * VIRALITY_VIEW_TO_FOLLOWER_WEIGHT,
        4,
    )


def compute_view_to_follower(views: int, follower_count: int | None) -> float:
    if follower_count is None or follower_count <= 0:
        return 0.0
    return round(views / follower_count, 4)


def compute_growth_rate(
    current_followers: int | None,
    prev_followers: int | None,
) -> tuple[float | None, str]:
    if current_followers is None or prev_followers is None:
        return None, "PARTIAL"
    if prev_followers <= 0:
        if current_followers > 0:
            return float(current_followers), "PARTIAL"
        return 0.0, "FULL"
    rate = ((current_followers - prev_followers) / prev_followers) * 100.0
    return round(rate, 4), "FULL"


def compute_posting_frequency(
    posts_count: int | None,
    prev_posts_count: int | None,
    time_period_days: int = 30,
) -> float | None:
    if posts_count is None or prev_posts_count is None:
        return None
    new_posts = posts_count - prev_posts_count
    if new_posts < 0:
        new_posts = 0
    weeks = max(time_period_days / 7.0, 0.1)
    return round(new_posts / weeks, 4)


def compute_avg_watch_time(
    duration_sec: float | None,
    views: int,
    total_watch_time_sec: float | None = None,
) -> float | None:
    if total_watch_time_sec is not None and views > 0:
        return round(total_watch_time_sec / views, 2)
    if duration_sec is not None and duration_sec > 0:
        return round(duration_sec * 0.5, 2)
    return None


def compute_content_consistency(
    current_topic: str | None,
    previous_topics: list[str] | None = None,
) -> float | None:
    if not current_topic:
        return None
    if previous_topics is None:
        return None
    if not previous_topics:
        return 0.0
    matches = sum(1 for t in previous_topics if t == current_topic)
    return round(matches / len(previous_topics), 4)


def compute_audience_growth(
    current_followers: int | None,
    prev_followers: int | None,
) -> int | None:
    if current_followers is None or prev_followers is None:
        return None
    return current_followers - prev_followers


def is_follower_count_volatile(follower_count: int | None) -> bool:
    if follower_count is None:
        return True
    return follower_count < FOLLOWER_VOLATILITY_THRESHOLD


def compute_reel_metrics(
    reel_id: str,
    views: int = 0,
    likes: int = 0,
    comments_count: int = 0,
    saves: int | None = None,
    shares: int | None = None,
    follower_count: int | None = None,
    prev_follower_count: int | None = None,
    duration_sec: float | None = None,
    avg_watch_time_sec: float | None = None,
    posts_count: int | None = None,
    prev_posts_count: int | None = None,
    time_period_days: int = 30,
    comments_disabled: bool = False,
    current_topic: str | None = None,
    previous_topics: list[str] | None = None,
) -> ReelMetricsResult:
    errors: list[str] = []
    partial_flags: list[str] = []

    engagement_rate, er_quality = compute_engagement_rate(
        likes, comments_count, saves, shares, views
    )
    if er_quality == "PARTIAL":
        partial_flags.append("engagement_rate")

    save_rate, sr_quality = compute_save_rate(saves, views)
    if sr_quality == "PARTIAL":
        partial_flags.append("save_rate")

    share_rate, shr_quality = compute_share_rate(shares, views)
    if shr_quality == "PARTIAL":
        partial_flags.append("share_rate")

    comment_rate, _ = compute_comment_rate(comments_count, views, comments_disabled)

    view_to_follower = compute_view_to_follower(views, follower_count)

    virality_score = compute_virality_score(
        engagement_rate, share_rate, view_to_follower
    )

    growth_rate, gr_quality = compute_growth_rate(follower_count, prev_follower_count)
    # ponytail: growth_rate/gr_quality intentionally excluded from
    # partial_flags — per spec, metricQuality is FULL/PARTIAL based only on
    # views/likes/commentsCount/saves/shares, not follower-history fields.

    posting_frequency = compute_posting_frequency(
        posts_count, prev_posts_count, time_period_days
    )

    avg_watch_time = compute_avg_watch_time(
        duration_sec, views, avg_watch_time_sec
    )

    content_consistency = compute_content_consistency(current_topic, previous_topics)

    audience_growth = compute_audience_growth(follower_count, prev_follower_count)

    is_volatile = is_follower_count_volatile(follower_count)
    metric_quality = "PARTIAL" if partial_flags else "FULL"

    for exc in errors:
        logger.error("metric_compute_error", reel_id=reel_id, error=exc)

    return ReelMetricsResult(
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
        growth_rate=growth_rate,
        posting_frequency=posting_frequency,
        avg_watch_time_sec=avg_watch_time,
        content_consistency=content_consistency,
        audience_growth=audience_growth,
        metric_quality=metric_quality,
        is_volatile=is_volatile,
        follower_count=follower_count,
        prev_follower_count=prev_follower_count,
    )