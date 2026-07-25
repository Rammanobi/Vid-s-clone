from __future__ import annotations

from typing import Any

from app.db import DatabaseClient
from app.logging_setup import get_logger

logger = get_logger(__name__)


async def fetch_competitor_strategies(
    db: DatabaseClient,
    niche: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    insights = await db.get_competitor_insights_by_niche(niche, limit=limit)
    logger.debug(
        "competitor_strategies_fetched",
        niche=niche,
        count=len(insights),
    )
    return insights


async def fetch_trending_data(
    db: DatabaseClient,
    topic: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    trends = await db.get_trends_by_topic(topic=topic, limit=limit)
    logger.debug(
        "trending_data_fetched",
        topic=topic or "all",
        count=len(trends),
    )
    return trends


def merge_competitor_trends(
    competitor_insights: list[dict[str, Any]],
    trend_data: list[dict[str, Any]],
) -> dict[str, Any]:
    emerging_formats: list[str] = []
    seen_formats: set[str] = set()
    for ci in competitor_insights:
        wf = ci.get("winningFormat")
        if wf and str(wf) not in seen_formats:
            emerging_formats.append(str(wf))
            seen_formats.add(str(wf))
    for td in trend_data:
        cf = td.get("contentFormat")
        if cf and str(cf) not in seen_formats:
            emerging_formats.append(str(cf))
            seen_formats.add(str(cf))

    trending_topics: list[str] = []
    seen_topics: set[str] = set()
    for td in trend_data:
        t = td.get("topic")
        if t and t not in seen_topics:
            trending_topics.append(t)
            seen_topics.add(t)
    for ci in competitor_insights:
        for t in (ci.get("topTopics") or []):
            if t not in seen_topics:
                trending_topics.append(t)
                seen_topics.add(t)

    competitor_strategies: list[dict[str, Any]] = []
    for ci in competitor_insights:
        competitor_strategies.append({
            "competitor_id": ci["competitorId"],
            "niche": ci.get("niche"),
            "winning_format": str(ci.get("winningFormat")) if ci.get("winningFormat") else None,
            "top_topics": ci.get("topTopics") or [],
            "avg_virality": ci.get("avgVirality") or 1.0,
        })

    trending_hooks: list[str] = []
    seen_hooks: set[str] = set()
    for td in trend_data:
        hp = td.get("hookPattern")
        if hp and hp not in seen_hooks:
            trending_hooks.append(hp)
            seen_hooks.add(hp)

    return {
        "competitor_strategies": competitor_strategies,
        "emerging_formats": emerging_formats,
        "trending_topics": trending_topics,
        "trending_hooks": trending_hooks,
        "trend_count": len(trend_data),
    }