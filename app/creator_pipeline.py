from __future__ import annotations

import json
import time
from typing import Any

from app.competitor_integration import (
    fetch_competitor_strategies,
    fetch_trending_data,
    merge_competitor_trends,
)
from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.monitoring import (
    creator_intelligence_errors_total,
    creator_intelligence_last_run_duration_seconds,
    creator_intelligence_last_run_timestamp,
    creator_intelligence_reels_processed_total,
    creator_intelligence_runs_total,
)
from app.patterns import analyze_patterns
from app.routes.creator import record_creator_intelligence_run, record_creator_intelligence_error

logger = get_logger(__name__)

DEFAULT_ACCOUNT_ID = "default"


async def build_creator_intelligence(
    db: DatabaseClient,
    account_id: str = DEFAULT_ACCOUNT_ID,
    limit: int = 200,
    trending_topic_filter: str | None = None,
) -> dict[str, Any]:
    reels = await db.get_reels_with_full_intelligence(limit=limit)
    logger.info("creator_intelligence_fetch", reel_count=len(reels))

    niche = reels[0].get("topic") if reels else None
    if not niche:
        for r in reels:
            t = r.get("topic") or r.get("transcript") or r.get("caption")
            if t:
                niche = t[:200]
                break

    competitor_insights = await fetch_competitor_strategies(
        db, niche=niche or "general", limit=20
    )
    trend_data = await fetch_trending_data(
        db, topic=trending_topic_filter, limit=20
    )

    trending_topics_set: list[str] = []
    seen: set[str] = set()
    for td in trend_data:
        t = td.get("topic")
        if t and t not in seen:
            trending_topics_set.append(t)
            seen.add(t)
    for ci in competitor_insights:
        for t in (ci.get("topTopics") or []):
            if t not in seen:
                trending_topics_set.append(t)
                seen.add(t)

    patterns = analyze_patterns(reels, trending_topics=trending_topics_set)
    competitor_trends = merge_competitor_trends(competitor_insights, trend_data)

    return {
        "account_id": account_id,
        "patterns": patterns,
        "competitor_trends": competitor_trends,
        "niche": niche,
    }


async def persist_creator_profile(
    db: DatabaseClient,
    intelligence: dict[str, Any],
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> dict[str, Any] | None:
    patterns = intelligence.get("patterns", {})
    competitor_trends = intelligence.get("competitor_trends", {})
    niche = intelligence.get("niche")

    best_topics = patterns.get("best_topics", [])
    worst_topics = patterns.get("worst_topics", [])
    best_hook_types = patterns.get("best_hook_types", [])
    best_posting_day = patterns.get("best_posting_day")
    best_duration_range = patterns.get("best_duration_range")

    best_formats = patterns.get("best_content_formats", [])
    best_content_format = best_formats[0] if best_formats else None

    audience_interests = patterns.get("audience_interests", [])

    if competitor_trends:
        trending_topics = competitor_trends.get("trending_topics", [])
        for t in trending_topics:
            t_lower = t.lower()
            if not any(ai.lower() == t_lower for ai in audience_interests):
                audience_interests.append(t)

    emerging_formats = competitor_trends.get("emerging_formats", [])
    if emerging_formats and not best_content_format:
        best_content_format = emerging_formats[0]

    result = await db.upsert_creator_profile(
        account_id=account_id,
        best_topics=best_topics,
        worst_topics=worst_topics,
        best_hook_types=best_hook_types,
        best_posting_day=best_posting_day,
        best_duration_range=best_duration_range,
        best_content_format=best_content_format,
        audience_interests=audience_interests,
    )
    return result


async def run_creator_intelligence_pipeline(
    db: DatabaseClient,
    account_id: str = DEFAULT_ACCOUNT_ID,
    limit: int = 200,
) -> dict[str, Any]:
    start = time.monotonic()
    logger.info("creator_intelligence_pipeline_started")

    try:
        intelligence = await build_creator_intelligence(
            db, account_id=account_id, limit=limit
        )
        profile = await persist_creator_profile(db, intelligence, account_id=account_id)

        elapsed = time.monotonic() - start
        record_creator_intelligence_run(
            duration_sec=elapsed,
            reels_processed=intelligence.get("patterns", {}).get("reel_count", 0),
            status="completed",
        )
        logger.info(
            "creator_intelligence_pipeline_completed",
            elapsed_sec=round(elapsed, 3),
            account_id=account_id,
            profile_updated=profile is not None,
        )

        return {
            "status": "completed",
            "elapsed_sec": round(elapsed, 3),
            "account_id": account_id,
            "reels_analyzed": intelligence.get("patterns", {}).get("reel_count", 0),
            "profile_updated": profile is not None,
            "patterns": intelligence.get("patterns"),
            "competitor_trends": intelligence.get("competitor_trends"),
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        record_creator_intelligence_error("pipeline_failure")
        record_creator_intelligence_run(
            duration_sec=elapsed, reels_processed=0, status="failed"
        )
        logger.error(
            "creator_intelligence_pipeline_failed",
            error=str(exc),
            elapsed_sec=round(elapsed, 3),
        )
        return {
            "status": "failed",
            "elapsed_sec": round(elapsed, 3),
            "error": str(exc),
        }


def format_creator_profile_output(profile: dict[str, Any] | None) -> str:
    if profile is None:
        return json.dumps({"error": "no_profile"}, indent=2)
    output = {
        "creator_id": profile.get("accountId"),
        "best_topics": profile.get("bestTopics", []),
        "worst_topics": profile.get("worstTopics", []),
        "best_hook_types": list(profile.get("bestHookTypes", [])),
        "best_posting_day": profile.get("bestPostingDay"),
        "best_duration_range": profile.get("bestDurationRange"),
        "best_content_format": str(profile.get("bestContentFormat")) if profile.get("bestContentFormat") else None,
        "audience_interests": profile.get("audienceInterests", []),
    }
    return json.dumps(output, indent=2)