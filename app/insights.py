from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


def analyze_winning_hooks(
    reels: list[dict[str, Any]],
    min_reels: int = 3,
) -> dict[str, Any]:
    if len(reels) < min_reels:
        return {"analysis_possible": False, "reason": f"need at least {min_reels} reels"}

    hook_engagement: defaultdict[str, list[float]] = defaultdict(list)
    hook_counts: Counter[str] = Counter()
    format_engagement: defaultdict[str, list[float]] = defaultdict(list)

    for reel in reels:
        intelligence = reel.get("intelligence") or {}
        metrics = reel.get("metrics") or {}
        hook_type = intelligence.get("hook_type") or intelligence.get("hookType")
        content_format = intelligence.get("content_format") or intelligence.get("contentFormat")
        engagement = metrics.get("engagement_rate", 0.0) or 0.0

        if hook_type and engagement is not None:
            hook_engagement[hook_type].append(engagement)
            hook_counts[hook_type] += 1

        if content_format and engagement is not None:
            format_engagement[content_format].append(engagement)

    def avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    winning_hooks = sorted(
        [
            {
                "hook_type": ht,
                "avg_engagement": avg(vals),
                "reel_count": hook_counts[ht],
            }
            for ht, vals in hook_engagement.items()
        ],
        key=lambda x: x["avg_engagement"],
        reverse=True,
    )

    winning_formats = sorted(
        [
            {
                "content_format": cf,
                "avg_engagement": avg(vals),
                "reel_count": len(vals),
            }
            for cf, vals in format_engagement.items()
        ],
        key=lambda x: x["avg_engagement"],
        reverse=True,
    )

    return {
        "analysis_possible": True,
        "total_reels": len(reels),
        "winning_hooks": winning_hooks[:5] if winning_hooks else [],
        "winning_formats": winning_formats[:5] if winning_formats else [],
        "most_used_hook": hook_counts.most_common(1)[0][0] if hook_counts else None,
    }


def analyze_narrative_patterns(
    reels: list[dict[str, Any]],
) -> dict[str, Any]:
    narratives: Counter[str] = Counter()
    teaching_styles: Counter[str] = Counter()
    sentiments: Counter[str] = Counter()

    for reel in reels:
        intel = reel.get("intelligence") or {}
        ns = intel.get("narrative_style") or intel.get("narrativeStyle")
        ts = intel.get("teaching_style") or intel.get("teachingStyle")
        st = intel.get("sentiment")

        if ns:
            narratives[ns] += 1
        if ts:
            teaching_styles[ts] += 1
        if st:
            sentiments[st] += 1

    return {
        "narrative_style_distribution": dict(narratives.most_common()),
        "teaching_style_distribution": dict(teaching_styles.most_common()),
        "sentiment_distribution": dict(sentiments.most_common()),
        "dominant_narrative": narratives.most_common(1)[0][0] if narratives else None,
        "dominant_teaching_style": teaching_styles.most_common(1)[0][0] if teaching_styles else None,
    }


def analyze_audience_behavior(
    reels: list[dict[str, Any]],
) -> dict[str, Any]:
    if not reels:
        return {}

    total_views = sum(r.get("views", 0) or 0 for r in reels)
    total_likes = sum(r.get("likes", 0) or 0 for r in reels)
    total_comments = sum(r.get("commentsCount", 0) or 0 for r in reels)
    total_saves = sum(r.get("saves", 0) or 0 for r in reels)
    total_shares = sum(r.get("shares", 0) or 0 for r in reels)

    reels_with_data = sum(
        1 for r in reels if (r.get("views", 0) or 0) > 0
    )
    if reels_with_data == 0:
        return {}

    return {
        "total_reels_analyzed": len(reels),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_saves": total_saves,
        "total_shares": total_shares,
        "avg_views_per_reel": round(total_views / reels_with_data, 2) if reels_with_data else 0,
        "avg_likes_per_reel": round(total_likes / reels_with_data, 2) if reels_with_data else 0,
        "avg_comments_per_reel": round(total_comments / reels_with_data, 2) if reels_with_data else 0,
        "like_to_view_ratio": round(total_likes / total_views * 100, 4) if total_views else 0.0,
        "save_to_view_ratio": round(total_saves / total_views * 100, 4) if total_views else 0.0,
    }


def extract_insights(
    reels: list[dict[str, Any]],
    min_reels: int = 3,
) -> dict[str, Any]:
    return {
        "winning_hooks_analysis": analyze_winning_hooks(reels, min_reels),
        "narrative_patterns": analyze_narrative_patterns(reels),
        "audience_behavior": analyze_audience_behavior(reels),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "reel_count": len(reels),
    }