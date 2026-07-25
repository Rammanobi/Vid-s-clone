from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.monitoring import (
    knowledge_consecutive_failures,
    knowledge_scheduler_running,
    pipeline_scheduler_running,
    pipeline_scheduler_consecutive_failures,
)

logger = get_logger(__name__)

ALERT_THRESHOLD = 3

_consecutive_failures: int = 0
_pipeline_consecutive_failures: int = 0


def get_consecutive_failures() -> int:
    return _consecutive_failures


def get_pipeline_consecutive_failures() -> int:
    return _pipeline_consecutive_failures


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


async def _run_scheduled_pipeline(db: DatabaseClient) -> dict[str, Any]:
    from app.pipeline import PipelineStage, run_pipeline

    logger.info("scheduled_pipeline_started")
    result = await run_pipeline(
        db,
        stages=[
            PipelineStage.ENRICHMENT,
            PipelineStage.ANALYTICS,
            PipelineStage.INTELLIGENCE,
            PipelineStage.KNOWLEDGE,
        ],
        enrichment_limit=10,
        analytics_limit=100,
        intelligence_limit=100,
        intelligence_use_llm=True,
        knowledge_limit=200,
    )
    logger.info(
        "scheduled_pipeline_completed",
        status=result.status,
        elapsed_sec=result.elapsed_sec,
        stages=[{"name": s.stage.value, "status": s.status} for s in result.stages],
    )
    return {
        "status": result.status,
        "pipeline_run_id": result.pipeline_run_id,
        "elapsed_sec": result.elapsed_sec,
        "stage_count": len(result.stages),
    }


async def pipeline_update_loop(db: DatabaseClient) -> None:
    global _pipeline_consecutive_failures
    interval_sec = settings.creator_update_interval_hours * 3600
    pipeline_scheduler_running.set(1)
    logger.info(
        "pipeline_update_scheduler_started",
        interval_hours=settings.creator_update_interval_hours,
    )
    while True:
        try:
            result = await _run_scheduled_pipeline(db)
            if result.get("status") == "failed":
                _pipeline_consecutive_failures += 1
                logger.error(
                    "scheduled_pipeline_failed",
                    consecutive_failures=_pipeline_consecutive_failures,
                )
            else:
                if _pipeline_consecutive_failures > 0:
                    logger.info(
                        "scheduled_pipeline_recovered",
                        cleared_failures=_pipeline_consecutive_failures,
                    )
                _pipeline_consecutive_failures = 0
        except Exception as exc:
            _pipeline_consecutive_failures += 1
            logger.error(
                "scheduled_pipeline_exception",
                error=str(exc),
                consecutive_failures=_pipeline_consecutive_failures,
            )
        if _pipeline_consecutive_failures >= ALERT_THRESHOLD:
            logger.warning(
                "scheduled_pipeline_alert",
                consecutive_failures=_pipeline_consecutive_failures,
                threshold=ALERT_THRESHOLD,
                message="Pipeline scheduler has exceeded failure alert threshold",
            )
        pipeline_scheduler_consecutive_failures.set(_pipeline_consecutive_failures)
        await asyncio.sleep(interval_sec)