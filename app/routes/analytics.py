from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.db import DatabaseClient
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
    db: DatabaseClient = Depends(lambda: None),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False
    reel_count = await db.get_reel_count() if db_ok else 0

    status = "healthy" if db_ok else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/analytics/health", status=status
    ).inc()

    return {
        "status": status,
        "database": "connected" if db_ok else "unavailable",
        "reel_count": reel_count,
        "last_run": _LAST_RUN["status"],
        "last_run_timestamp": _LAST_RUN["timestamp"],
        "last_run_duration_sec": _LAST_RUN["duration_sec"],
        "last_run_reels_processed": _LAST_RUN["reels_processed"],
        "version": "1.0.0",
    }