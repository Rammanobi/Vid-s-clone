from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from app.logging_setup import get_logger

logger = get_logger(__name__)

MIN_REELS_FOR_PATTERNS = 3
TOP_N = 3
DURATION_BUCKETS = [
    (0, 15, "0-15 sec"),
    (15, 30, "15-30 sec"),
    (30, 45, "30-45 sec"),
    (45, 60, "45-60 sec"),
    (60, 90, "60-90 sec"),
    (90, float("inf"), "90+ sec"),
]
POSTING_DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def _duration_bucket(duration_sec: float | None) -> str | None:
    if duration_sec is None or duration_sec < 0:
        return None
    for lo, hi, label in DURATION_BUCKETS:
        if lo <= duration_sec < hi:
            return label
    return None


def _posting_day(posted_at: Any) -> str | None:
    if posted_at is None:
        return None
    if isinstance(posted_at, datetime):
        return POSTING_DAY_NAMES[posted_at.weekday()]
    if isinstance(posted_at, str):
        try:
            dt = datetime.fromisoformat(posted_at)
            return POSTING_DAY_NAMES[dt.weekday()]
        except (ValueError, TypeError):
            return None
    return None


def _engagement_for_reel(reel: dict[str, Any]) -> float:
    return reel.get("engagementRate") or reel.get("engagement_rate") or 0.0


def _virality_for_reel(reel: dict[str, Any]) -> float:
    return reel.get("viralityScore") or reel.get("virality_score") or 0.0


def _topic_for_reel(reel: dict[str, Any]) -> str | None:
    return reel.get("topic") or None


def _hook_type_for_reel(reel: dict[str, Any]) -> str | None:
    ht = reel.get("hookType") or reel.get("hook_type")
    return str(ht) if ht else None


def _content_format_for_reel(reel: dict[str, Any]) -> str | None:
    cf = reel.get("contentFormat") or reel.get("content_format")
    return str(cf) if cf else None


def _audience_intent_for_reel(reel: dict[str, Any]) -> str | None:
    ai = reel.get("audienceIntent") or reel.get("audience_intent")
    return str(ai) if ai else None


def _sentiment_for_reel(reel: dict[str, Any]) -> str | None:
    s = reel.get("sentiment")
    return str(s) if s else None


def find_best_topics(
    reels: list[dict[str, Any]],
    top_n: int = TOP_N,
) -> list[str]:
    topic_engagement: defaultdict[str, list[float]] = defaultdict(list)
    for reel in reels:
        topic = _topic_for_reel(reel)
        if topic:
            topic_engagement[topic].append(_engagement_for_reel(reel))
    if not topic_engagement:
        return []
    averages = {t: statistics.mean(vals) for t, vals in topic_engagement.items()}
    sorted_topics = sorted(averages, key=averages.get, reverse=True)
    return sorted_topics[:top_n]


def find_worst_topics(
    reels: list[dict[str, Any]],
    top_n: int = TOP_N,
) -> list[str]:
    topic_engagement: defaultdict[str, list[float]] = defaultdict(list)
    for reel in reels:
        topic = _topic_for_reel(reel)
        if topic:
            topic_engagement[topic].append(_engagement_for_reel(reel))
    if not topic_engagement:
        return []
    averages = {t: statistics.mean(vals) for t, vals in topic_engagement.items()}
    sorted_topics = sorted(averages, key=averages.get)
    return sorted_topics[:top_n]


def find_best_hook_types(
    reels: list[dict[str, Any]],
    top_n: int = TOP_N,
) -> list[str]:
    hook_engagement: defaultdict[str, list[float]] = defaultdict(list)
    for reel in reels:
        hook = _hook_type_for_reel(reel)
        if hook:
            hook_engagement[hook].append(_engagement_for_reel(reel))
    if not hook_engagement:
        return []
    averages = {h: statistics.mean(vals) for h, vals in hook_engagement.items()}
    sorted_hooks = sorted(averages, key=averages.get, reverse=True)
    return sorted_hooks[:top_n]


def find_best_content_formats(
    reels: list[dict[str, Any]],
    top_n: int = TOP_N,
) -> list[str]:
    format_engagement: defaultdict[str, list[float]] = defaultdict(list)
    for reel in reels:
        cf = _content_format_for_reel(reel)
        if cf:
            format_engagement[cf].append(_engagement_for_reel(reel))
    if not format_engagement:
        return []
    averages = {f: statistics.mean(vals) for f, vals in format_engagement.items()}
    sorted_formats = sorted(averages, key=averages.get, reverse=True)
    return sorted_formats[:top_n]


def find_best_posting_day(reels: list[dict[str, Any]]) -> str | None:
    day_engagement: defaultdict[str, list[float]] = defaultdict(list)
    for reel in reels:
        day = _posting_day(reel.get("postedAt"))
        if day:
            day_engagement[day].append(_engagement_for_reel(reel))
    if not day_engagement:
        return None
    averages = {d: statistics.mean(vals) for d, vals in day_engagement.items()}
    return max(averages, key=averages.get)


def find_best_duration_range(reels: list[dict[str, Any]]) -> str | None:
    duration_engagement: defaultdict[str, list[float]] = defaultdict(list)
    for reel in reels:
        bucket = _duration_bucket(reel.get("durationSec") or reel.get("duration_sec"))
        if bucket:
            duration_engagement[bucket].append(_engagement_for_reel(reel))
    if not duration_engagement:
        return None
    averages = {d: statistics.mean(vals) for d, vals in duration_engagement.items()}
    return max(averages, key=averages.get)


def find_audience_interests(
    reels: list[dict[str, Any]],
    top_n: int = TOP_N,
) -> list[str]:
    topic_freq: Counter[str] = Counter()
    for reel in reels:
        topic = _topic_for_reel(reel)
        if topic:
            topic_freq[topic] += 1
    if not topic_freq:
        intent_freq: Counter[str] = Counter()
        for reel in reels:
            intent = _audience_intent_for_reel(reel)
            if intent:
                intent_freq[intent] += 1
        if intent_freq:
            return [item[0] for item in intent_freq.most_common(top_n)]
        return []
    return [item[0] for item in topic_freq.most_common(top_n)]


def detect_seasonal_trends(
    reels: list[dict[str, Any]],
) -> dict[str, Any]:
    month_engagement: defaultdict[int, list[float]] = defaultdict(list)
    for reel in reels:
        posted_at = reel.get("postedAt")
        if posted_at:
            dt = posted_at if isinstance(posted_at, datetime) else None
            if dt is None and isinstance(posted_at, str):
                try:
                    dt = datetime.fromisoformat(posted_at)
                except (ValueError, TypeError):
                    pass
            if dt:
                month_engagement[dt.month].append(_engagement_for_reel(reel))
    if not month_engagement:
        return {"seasonal_trends_possible": False}
    averages = {m: statistics.mean(vals) for m, vals in month_engagement.items()}
    best_month = max(averages, key=averages.get)
    worst_month = min(averages, key=averages.get)
    return {
        "seasonal_trends_possible": True,
        "monthly_avg_engagement": {
            str(m): round(v, 4) for m, v in sorted(averages.items())
        },
        "best_month": best_month,
        "worst_month": worst_month,
        "best_month_engagement": round(averages[best_month], 4),
        "worst_month_engagement": round(averages[worst_month], 4),
    }


def detect_content_gaps(
    reels: list[dict[str, Any]],
    trending_topics: list[str] | None = None,
) -> list[str]:
    existing_topics = {_topic_for_reel(r) for r in reels if _topic_for_reel(r)}
    existing_intents = {_audience_intent_for_reel(r) for r in reels if _audience_intent_for_reel(r)}
    existing_formats = {_content_format_for_reel(r) for r in reels if _content_format_for_reel(r)}
    missing_topics: list[str] = []
    if trending_topics:
        for t in trending_topics:
            t_lower = t.lower()
            if not any(e.lower() == t_lower for e in existing_topics):
                missing_topics.append(t)
    high_engagement_intents = {"educational", "inspiring", "entertaining"}
    missing_intents = high_engagement_intents - existing_intents
    gaps: list[str] = list(missing_topics)
    for mi in missing_intents:
        gaps.append(f"untapped_intent:{mi}")
    return gaps


def analyze_patterns(
    reels: list[dict[str, Any]],
    trending_topics: list[str] | None = None,
) -> dict[str, Any]:
    if len(reels) < MIN_REELS_FOR_PATTERNS:
        return {"analysis_possible": False, "reel_count": len(reels)}

    best_topics = find_best_topics(reels)
    worst_topics = find_worst_topics(reels)
    best_hooks = find_best_hook_types(reels)
    best_formats = find_best_content_formats(reels)
    best_day = find_best_posting_day(reels)
    best_duration = find_best_duration_range(reels)
    interests = find_audience_interests(reels)
    seasonal = detect_seasonal_trends(reels)
    gaps = detect_content_gaps(reels, trending_topics)

    return {
        "analysis_possible": True,
        "reel_count": len(reels),
        "best_topics": best_topics,
        "worst_topics": worst_topics,
        "best_hook_types": best_hooks,
        "best_content_formats": best_formats,
        "best_posting_day": best_day,
        "best_duration_range": best_duration,
        "audience_interests": interests,
        "seasonal_trends": seasonal,
        "content_gaps": gaps,
    }