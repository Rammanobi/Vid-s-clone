from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.monitoring import (
    knowledge_consecutive_failures,
    knowledge_scheduler_running,
)

logger = get_logger(__name__)

ALERT_THRESHOLD = 3

_consecutive_failures: int = 0


def get_consecutive_failures() -> int:
    return _consecutive_failures


async def _daily_creator_update(db: DatabaseClient) -> dict[str, Any]:
    from app.creator_pipeline import run_creator_intelligence_pipeline

    logger.info("scheduled_creator_update_started")
    result = await run_creator_intelligence_pipeline(db, limit=200)
    logger.info(
        "scheduled_creator_update_completed",
        status=result.get("status"),
        reels_analyzed=result.get("reels_analyzed"),
    )
    return result


async def creator_update_loop(db: DatabaseClient) -> None:
    global _consecutive_failures
    interval_sec = settings.creator_update_interval_hours * 3600
    knowledge_scheduler_running.set(1)
    logger.info(
        "creator_update_scheduler_started",
        interval_hours=settings.creator_update_interval_hours,
    )
    while True:
        try:
            result = await _daily_creator_update(db)
            if result.get("status") == "failed":
                _consecutive_failures += 1
                logger.error(
                    "scheduled_creator_update_failed",
                    consecutive_failures=_consecutive_failures,
                )
            else:
                if _consecutive_failures > 0:
                    logger.info(
                        "scheduled_creator_update_recovered",
                        cleared_failures=_consecutive_failures,
                    )
                _consecutive_failures = 0
        except Exception as exc:
            _consecutive_failures += 1
            logger.error(
                "scheduled_creator_update_exception",
                error=str(exc),
                consecutive_failures=_consecutive_failures,
            )
        if _consecutive_failures >= ALERT_THRESHOLD:
            logger.warning(
                "scheduled_creator_update_alert",
                consecutive_failures=_consecutive_failures,
                threshold=ALERT_THRESHOLD,
                message="Knowledge scheduler has exceeded failure alert threshold",
            )
        knowledge_consecutive_failures.set(_consecutive_failures)
        await asyncio.sleep(interval_sec)