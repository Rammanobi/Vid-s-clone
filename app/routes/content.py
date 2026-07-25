from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

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
            reels = await db.get_reels_with_metrics(limit=999999)
            all_metrics_result = await db.get_reel_metrics(
                [r["id"] for r in reels]
            )
            intelligence_count = sum(
                1 for m in all_metrics_result if m.get("content_intelligence_id") is not None
            )
        except Exception:
            pass

    status = "healthy" if db_ok else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/content/health", status=status
    ).inc()

    return {
        "status": status,
        "database": "connected" if db_ok else "unavailable",
        "reel_count": reel_count,
        "intelligence_count": intelligence_count,
        "last_run": _LAST_RUN["status"],
        "last_run_timestamp": _LAST_RUN["timestamp"],
        "last_run_duration_sec": _LAST_RUN["duration_sec"],
        "last_run_reels_processed": _LAST_RUN["reels_processed"],
        "version": "1.0.0",
    }