from __future__ import annotations

import statistics
from typing import Any

from app.db import DatabaseClient
from app.graph.registry import ToolInfo, registry
from app.logging_setup import get_logger

logger = get_logger(__name__)


async def get_creator_knowledge(
    db: DatabaseClient,
    account_id: str = "default",
) -> dict[str, Any]:
    profile = await db.get_creator_profile(account_id)
    if not profile:
        return {}
    return {
        "best_topics": profile.get("bestTopics", []),
        "worst_topics": profile.get("worstTopics", []),
        "best_hook_types": list(profile.get("bestHookTypes", [])),
        "best_posting_day": profile.get("bestPostingDay"),
        "best_duration_range": profile.get("bestDurationRange"),
        "best_content_format": (
            str(profile["bestContentFormat"])
            if profile.get("bestContentFormat")
            else None
        ),
        "audience_interests": profile.get("audienceInterests", []),
    }


async def get_analytics(
    db: DatabaseClient,
    limit: int = 50,
) -> dict[str, Any]:
    reels = await db.get_reels_with_metrics(limit=limit)
    if not reels:
        return {"reel_count": 0}
    engagement_rates = [
        r.get("engagementRate") or 0.0 for r in reels
    ]
    virality_scores = [
        r.get("viralityScore") or 0.0 for r in reels
    ]
    return {
        "reel_count": len(reels),
        "avg_engagement_rate": round(statistics.mean(engagement_rates), 4),
        "avg_virality_score": round(statistics.mean(virality_scores), 4),
        "total_views": sum(r.get("views", 0) or 0 for r in reels),
        "total_likes": sum(r.get("likes", 0) or 0 for r in reels),
    }


async def hybrid_search(
    db: DatabaseClient,
    query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    reels = await db.get_reels_with_full_intelligence(limit=limit)

    if not query:
        return reels[:5]

    query_lower = query.lower()
    query_terms = query_lower.split()

    scored: list[tuple[float, dict[str, Any]]] = []
    for reel in reels:
        score = 0.0
        caption = (reel.get("caption") or "").lower()
        transcript = (reel.get("transcript") or "").lower()
        topic = (reel.get("topic") or "").lower()
        hook_text = (reel.get("hookText") or "").lower()
        searchable_text = f"{caption} {transcript} {topic} {hook_text}"

        for term in query_terms:
            if term in searchable_text:
                score += 1.0
            for word in searchable_text.split():
                if word.startswith(term):
                    score += 0.5
                    break

        if score > 0:
            scored.append((score, reel))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored[:5]]


async def get_competitor_insights(
    db: DatabaseClient,
    niche: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if niche:
        return await db.get_competitor_insights_by_niche(niche, limit=limit)

    results = await db.get_competitor_insights_by_niche("general", limit=limit)
    if results:
        return results
    return []


async def get_trending_data(
    db: DatabaseClient,
    topic: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    return await db.get_trends_by_topic(topic=topic, limit=limit)


async def get_conversation_memory(
    db: DatabaseClient,
    session_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    messages = await db.get_chat_messages(session_id, limit=limit)
    session = await db.get_session(session_id)
    return {
        "session": dict(session) if session else None,
        "messages": messages,
        "message_count": len(messages),
    }


registry.register(ToolInfo(
    name="creator_knowledge",
    description="Creator's best topics, hooks, posting patterns, and audience interests",
    func=get_creator_knowledge,
    read_only=True,
    param_names=["account_id"],
))
registry.register(ToolInfo(
    name="analytics",
    description="Performance metrics: engagement rate, virality score, views, likes across reels",
    func=get_analytics,
    read_only=True,
    param_names=["limit"],
))
registry.register(ToolInfo(
    name="hybrid_search",
    description="Text-scored semantic search across reel transcripts, captions, topics, and hook text",
    func=hybrid_search,
    read_only=True,
    param_names=["query", "limit"],
))
registry.register(ToolInfo(
    name="competitor",
    description="Competitor strategies, winning formats, top topics, and virality benchmarks by niche",
    func=get_competitor_insights,
    read_only=True,
    param_names=["niche", "limit"],
))
registry.register(ToolInfo(
    name="trends",
    description="Trending topics, hook patterns, content formats sorted by virality score",
    func=get_trending_data,
    read_only=True,
    param_names=["topic", "limit"],
))
registry.register(ToolInfo(
    name="conversation_memory",
    description="Session chat history, summary, and message count for conversation continuity",
    func=get_conversation_memory,
    read_only=True,
    param_names=["session_id", "limit"],
))
