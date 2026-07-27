from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import (
    creator_intelligence_errors_total,
    creator_intelligence_last_run_duration_seconds,
    creator_intelligence_last_run_timestamp,
    creator_intelligence_runs_total,
    http_request_duration_seconds,
    http_requests_total,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/creator", tags=["creator"])

_LAST_RUN: dict[str, Any] = {
    "timestamp": None,
    "duration_sec": None,
    "reels_processed": 0,
    "status": "never_run",
}


def record_creator_intelligence_run(
    duration_sec: float,
    reels_processed: int,
    status: str,
) -> None:
    ts = time.time()
    _LAST_RUN["timestamp"] = ts
    _LAST_RUN["duration_sec"] = duration_sec
    _LAST_RUN["reels_processed"] = reels_processed
    _LAST_RUN["status"] = status
    creator_intelligence_last_run_timestamp.set(ts)
    creator_intelligence_last_run_duration_seconds.set(duration_sec)
    creator_intelligence_runs_total.labels(status=status).inc()


def record_creator_intelligence_error(error_type: str) -> None:
    creator_intelligence_errors_total.labels(error_type=error_type).inc()


@router.get("/health")
async def creator_health(
    db: DatabaseClient = Depends(get_db_dependency),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False
    reel_count = await db.get_reel_count() if db_ok else 0

    profile = None
    if db_ok:
        try:
            primary_account_id = await db.get_primary_account_id()
            if primary_account_id:
                profile = await db.get_creator_profile(primary_account_id)
        except Exception:
            pass

    is_healthy = db_ok
    status_str = "healthy" if is_healthy else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/creator/health", status=status_str
    ).inc()

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Creator health check failed",
        )

    return {
        "status": status_str,
        "database": "connected" if db_ok else "unavailable",
        "reel_count": reel_count,
        "profile_exists": profile is not None,
        "last_run": _LAST_RUN["status"],
        "last_run_timestamp": _LAST_RUN["timestamp"],
        "last_run_duration_sec": _LAST_RUN["duration_sec"],
        "last_run_reels_processed": _LAST_RUN["reels_processed"],
        "version": "1.0.0",
    }