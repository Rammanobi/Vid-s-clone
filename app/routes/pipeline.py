from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.pipeline import PipelineStage, run_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/health")
async def pipeline_health(
    db: Any = Depends(get_db_dependency),
) -> dict[str, Any]:
    from app.scheduler import get_pipeline_consecutive_failures

    fails = get_pipeline_consecutive_failures()
    is_healthy = fails == 0
    status_str = "healthy" if is_healthy else "degraded"

    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pipeline health check failed",
        )

    return {
        "status": status_str,
        "pipeline": {
            "scheduler_running": True,
            "consecutive_failures": fails,
            "alert_threshold": 3,
        },
        "stages": [s.value for s in PipelineStage],
    }


@router.post("/run", status_code=202)
async def trigger_pipeline(
    stages: list[str] | None = Query(None),
    db: Any = Depends(get_db_dependency),
) -> dict[str, Any]:
    stage_enums = None
    if stages:
        stage_enums = [PipelineStage(s) for s in stages]

    result = await run_pipeline(db, stages=stage_enums)

    return {
        "pipeline_run_id": result.pipeline_run_id,
        "status": result.status,
        "elapsed_sec": result.elapsed_sec,
        "stages": [
            {
                "name": s.stage.value,
                "status": s.status,
                "elapsed_sec": s.elapsed_sec,
                "error": s.error,
            }
            for s in result.stages
        ],
        "stages_order": [s.value for s in PipelineStage],
    }


@router.get("/stages")
async def list_stages() -> dict[str, Any]:
    return {
        "stages": [s.value for s in PipelineStage],
        "description": {
            "ingestion": "Ingest reels from Hiker API",
            "enrichment": "Enrich reels with transcription, OCR, CLIP",
            "analytics": "Compute metrics and snapshots",
            "intelligence": "Extract content intelligence via LLM",
            "knowledge": "Build creator knowledge profile",
            "agent": "Verify LangGraph agent compilation",
            "retrieval": "Verify hybrid retrieval pipeline",
        },
    }
