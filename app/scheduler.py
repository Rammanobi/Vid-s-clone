from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.db import DatabaseClient
from app.logging_setup import get_logger

logger = get_logger(__name__)


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
    interval_sec = settings.creator_update_interval_hours * 3600
    logger.info(
        "creator_update_scheduler_started",
        interval_hours=settings.creator_update_interval_hours,
    )
    while True:
        try:
            await _daily_creator_update(db)
        except Exception as exc:
            logger.error("scheduled_creator_update_failed", error=str(exc))
        await asyncio.sleep(interval_sec)