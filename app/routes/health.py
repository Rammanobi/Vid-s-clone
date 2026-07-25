from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import http_request_duration_seconds, http_requests_total

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(
    db: DatabaseClient = Depends(get_db_dependency),
) -> dict[str, Any]:
    db_ok = await db.health() if db is not None else False

    status_code = "healthy" if db_ok else "degraded"
    http_requests_total.labels(
        method="GET", endpoint="/health", status=status_code
    ).inc()

    return {
        "status": status_code,
        "database": "connected" if db_ok else "unavailable",
        "version": "1.0.0",
    }