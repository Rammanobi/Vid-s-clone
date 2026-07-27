from __future__ import annotations

import statistics
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import (
    analytics_errors_total,
    analytics_last_run_duration_seconds,
    analytics_last_run_timestamp,
    analytics_runs_total,
    http_request_duration_seconds,
    http_requests_total,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_LAST_RUN: dict[str, Any] = {
    "timestamp": None,
    "duration_sec": None,
    "reels_processed": 0,
    "status": "never_run",
}


def record_analytics_run(
    duration_sec: float,
    reels_processed: int,
    status: str,
) -> None:
    import time

    ts = time.time()
    _LAST_RUN["timestamp"] = ts
    _LAST_RUN["duration_sec"] = duration_sec
    _LAST_RUN["reels_processed"] = reels_processed
    _LAST_RUN["status"] = status
    analytics_last_run_timestamp.set(ts)
    analytics_last_run_duration_seconds.set(duration_sec)
    analytics_runs_total.labels(status=status).inc()


def record_analytics_error(error_type: str) -> None:
    analytics_errors_total.labels(error_type=error_type).inc()


@router.get("/health")
async def analytics_health(
    db: DatabaseClient = Depends(get_db_dependency),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False
    reel_count = await db.get_reel_count() if db_ok else 0

    is_healthy = db_ok
    status_str = "healthy" if is_healthy else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/analytics/health", status=status_str
    ).inc()

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics health check failed",
        )

    return {
        "status": status_str,
        "database": "connected" if db_ok else "unavailable",
        "reel_count": reel_count,
        "last_run": _LAST_RUN["status"],
        "last_run_timestamp": _LAST_RUN["timestamp"],
        "last_run_duration_sec": _LAST_RUN["duration_sec"],
        "last_run_reels_processed": _LAST_RUN["reels_processed"],
        "version": "1.0.0",
    }


@router.get("/summary")
async def analytics_summary(
    limit: int = Query(100, ge=1, le=1000),
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Real aggregate numbers for the dashboard - this is the endpoint the
    frontend's Analytics page needs and previously never had; it only ever
    had /health, which carries no metric data at all."""
    reels = await db.get_reels_with_metrics(limit=limit) if db is not None else []

    if not reels:
        return {
            "total_reels": 0,
            "total_accounts": 0,
            "avg_engagement_rate": 0.0,
            "avg_virality_score": 0.0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_saves": 0,
            "total_shares": 0,
            "top_reels": [],
            "reels": [],
        }

    engagement_rates = [r.get("engagementRate") or 0.0 for r in reels]
    virality_scores = [r.get("viralityScore") or 0.0 for r in reels]

    top_reels = sorted(
        reels, key=lambda r: r.get("engagementRate") or 0.0, reverse=True
    )[:5]

    http_requests_total.labels(
        method="GET", endpoint="/analytics/summary", status="200"
    ).inc()

    return {
        "total_reels": len(reels),
        # Single-primary-account tool (see app/db.py::get_primary_account_id) -
        # not real multi-tenancy, so this is 1 whenever any reel exists.
        "total_accounts": 1,
        "avg_engagement_rate": round(statistics.mean(engagement_rates), 4),
        "avg_virality_score": round(statistics.mean(virality_scores), 4),
        "total_views": sum(r.get("views", 0) or 0 for r in reels),
        "total_likes": sum(r.get("likes", 0) or 0 for r in reels),
        "total_comments": sum(r.get("commentsCount", 0) or 0 for r in reels),
        "total_saves": sum(r.get("saves", 0) or 0 for r in reels),
        "total_shares": sum(r.get("shares", 0) or 0 for r in reels),
        "top_reels": [
            {
                "id": r.get("id"),
                "instagram_reel_id": r.get("instagramReelId"),
                "video_url": r.get("videoUrl"),
                "views": r.get("views", 0) or 0,
                "likes": r.get("likes", 0) or 0,
                "engagement_rate": r.get("engagementRate") or 0.0,
                "virality_score": r.get("viralityScore") or 0.0,
                "posted_at": r.get("postedAt").isoformat() if r.get("postedAt") else None,
            }
            for r in top_reels
        ],
        "reels": [
            {
                "id": r.get("id"),
                "instagram_reel_id": r.get("instagramReelId"),
                "video_url": r.get("videoUrl"),
                "views": r.get("views", 0) or 0,
                "likes": r.get("likes", 0) or 0,
                "comments_count": r.get("commentsCount", 0) or 0,
                "saves": r.get("saves", 0) or 0,
                "shares": r.get("shares", 0) or 0,
                "engagement_rate": r.get("engagementRate") or 0.0,
                "virality_score": r.get("viralityScore") or 0.0,
                "posted_at": r.get("postedAt").isoformat() if r.get("postedAt") else None,
            }
            for r in reels
        ],
    }