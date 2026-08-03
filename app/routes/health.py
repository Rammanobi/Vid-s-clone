from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.cache import get_redis
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import http_requests_total

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(
    db: DatabaseClient = Depends(get_db_dependency),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False

    redis_ok = False
    try:
        r = get_redis()
        if r is not None:
            await r.ping()
            redis_ok = True
    except Exception:
        redis_ok = False

    # Only the database is required to call this service healthy. Redis is a
    # cache: every read falls back to the DB when it's absent, so a missing
    # Redis degrades speed, not correctness. Gating 503 on redis_ok too meant
    # production - which has no Redis instance provisioned - reported itself
    # permanently down, and the dashboard's own status tiles read this
    # endpoint, so a working deployment showed every service "Unreachable".
    is_healthy = db_ok
    status_code = "healthy" if (db_ok and redis_ok) else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/health", status=status_code
    ).inc()

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed",
        )

    return {
        "status": status_code,
        "database": "connected" if db_ok else "unavailable",
        "redis": "connected" if redis_ok else "unavailable",
        "version": "1.0.0",
    }