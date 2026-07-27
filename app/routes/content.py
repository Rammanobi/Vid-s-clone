from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import (
    content_intelligence_errors_total,
    content_intelligence_last_run_duration_seconds,
    content_intelligence_last_run_timestamp,
    content_intelligence_runs_total,
    http_request_duration_seconds,
    http_requests_total,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/content", tags=["content"])

_LAST_RUN: dict[str, Any] = {
    "timestamp": None,
    "duration_sec": None,
    "reels_processed": 0,
    "status": "never_run",
}


def record_content_intelligence_run(
    duration_sec: float,
    reels_processed: int,
    status: str,
) -> None:
    ts = time.time()
    _LAST_RUN["timestamp"] = ts
    _LAST_RUN["duration_sec"] = duration_sec
    _LAST_RUN["reels_processed"] = reels_processed
    _LAST_RUN["status"] = status
    content_intelligence_last_run_timestamp.set(ts)
    content_intelligence_last_run_duration_seconds.set(duration_sec)
    content_intelligence_runs_total.labels(status=status).inc()


def record_content_intelligence_error(error_type: str) -> None:
    content_intelligence_errors_total.labels(error_type=error_type).inc()


@router.get("/health")
async def content_health(
    db: DatabaseClient = Depends(get_db_dependency),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False
    reel_count = await db.get_reel_count() if db_ok else 0

    intelligence_count = 0
    if db_ok:
        try:
            reels_with_intel = await db.get_reels_with_content_intelligence(limit=100)
            intelligence_count = sum(
                1 for r in reels_with_intel if r.get("topic") is not None
            )
        except Exception:
            pass

    is_healthy = db_ok
    status_str = "healthy" if is_healthy else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/content/health", status=status_str
    ).inc()

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Content health check failed",
        )

    return {
        "status": status_str,
        "database": "connected" if db_ok else "unavailable",
        "reel_count": reel_count,
        "intelligence_count": intelligence_count,
        "last_run": _LAST_RUN["status"],
        "last_run_timestamp": _LAST_RUN["timestamp"],
        "last_run_duration_sec": _LAST_RUN["duration_sec"],
        "last_run_reels_processed": _LAST_RUN["reels_processed"],
        "version": "1.0.0",
    }


@router.get("/reels")
async def content_reels(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """List reels with metrics + content intelligence (topic, hook type,
    format, etc.) for the frontend's Content page - previously this page
    rendered a hardcoded placeholder array with no backend endpoint at all."""
    reels = (
        await db.get_reels_with_content_intelligence(limit=limit, offset=offset)
        if db is not None
        else []
    )

    http_requests_total.labels(
        method="GET", endpoint="/content/reels", status="200"
    ).inc()

    return {
        "reels": [
            {
                "id": r.get("id"),
                "instagram_reel_id": r.get("instagramReelId"),
                "video_url": r.get("videoUrl"),
                "caption": r.get("caption"),
                "views": r.get("views", 0) or 0,
                "likes": r.get("likes", 0) or 0,
                "comments_count": r.get("commentsCount", 0) or 0,
                "engagement_rate": r.get("engagementRate") or 0.0,
                "virality_score": r.get("viralityScore") or 0.0,
                "topic": r.get("topic"),
                "hook_type": r.get("hookType"),
                "hook_text": r.get("hookText"),
                "cta": r.get("cta"),
                "content_format": r.get("contentFormat"),
                "sentiment": r.get("sentiment"),
                "posted_at": r.get("postedAt").isoformat() if r.get("postedAt") else None,
            }
            for r in reels
        ],
        "count": len(reels),
    }