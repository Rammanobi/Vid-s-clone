from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.monitoring import (
    creator_intelligence_errors_total,
    creator_intelligence_last_run_duration_seconds,
    creator_intelligence_last_run_timestamp,
    creator_intelligence_runs_total,
    http_requests_total,
    knowledge_consecutive_failures,
    knowledge_scheduler_running,
)
from app.routes.creator import _LAST_RUN as _CREATOR_LAST_RUN
from app.scheduler import ALERT_THRESHOLD

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/health")
async def knowledge_health(
    db: DatabaseClient = Depends(lambda: None),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False
    reel_count = await db.get_reel_count() if db_ok else 0

    profile = None
    if db_ok:
        try:
            profile = await db.get_creator_profile("default")
        except Exception:
            pass

    consecutive_failures = int(knowledge_consecutive_failures._value.get())
    scheduler_running = knowledge_scheduler_running._value.get() == 1.0

    alerts: list[str] = []
    if not db_ok:
        alerts.append("database_unavailable")
    if consecutive_failures >= ALERT_THRESHOLD:
        alerts.append("scheduler_excessive_failures")

    status = "healthy"
    if not db_ok or consecutive_failures >= ALERT_THRESHOLD:
        status = "degraded"

    http_requests_total.labels(
        method="GET", endpoint="/knowledge/health", status=status
    ).inc()

    return {
        "status": status,
        "database": "connected" if db_ok else "unavailable",
        "reel_count": reel_count,
        "profile_exists": profile is not None,
        "scheduler": {
            "running": scheduler_running,
            "consecutive_failures": consecutive_failures,
            "alert_threshold": ALERT_THRESHOLD,
        },
        "last_run": _CREATOR_LAST_RUN["status"],
        "last_run_timestamp": _CREATOR_LAST_RUN["timestamp"],
        "last_run_duration_sec": _CREATOR_LAST_RUN["duration_sec"],
        "last_run_reels_processed": _CREATOR_LAST_RUN["reels_processed"],
        "alerts": alerts,
        "version": "1.0.0",
    }