from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from app.config import settings
from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.monitoring import (
    pipeline_last_run_duration_seconds,
    pipeline_last_run_timestamp,
    pipeline_run_duration_seconds,
    pipeline_runs_total,
    pipeline_stage_duration_seconds,
    pipeline_stage_errors_total,
    pipeline_stage_status,
)

logger = get_logger(__name__)

DEFAULT_INGESTION_MAX_REELS = 50
DEFAULT_INGESTION_MAX_COMMENTS = 200
DEFAULT_INGESTION_USERNAMES: list[str] = []


class PipelineStage(str, Enum):
    INGESTION = "ingestion"
    ENRICHMENT = "enrichment"
    ANALYTICS = "analytics"
    INTELLIGENCE = "intelligence"
    KNOWLEDGE = "knowledge"
    AGENT = "agent"
    RETRIEVAL = "retrieval"

    def __str__(self) -> str:
        return self.value


@dataclass
class StageResult:
    stage: PipelineStage
    status: Literal["success", "skipped", "failed"]
    elapsed_sec: float = 0.0
    details: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class PipelineResult:
    pipeline_run_id: str
    status: Literal["success", "partial", "failed"]
    stages: list[StageResult] = field(default_factory=list)
    elapsed_sec: float = 0.0


async def run_ingestion_stage(
    db: DatabaseClient,
    usernames: list[str] | None = None,
    max_reels: int = DEFAULT_INGESTION_MAX_REELS,
    max_comments: int = DEFAULT_INGESTION_MAX_COMMENTS,
) -> StageResult:
    stage = PipelineStage.INGESTION
    usernames = usernames or DEFAULT_INGESTION_USERNAMES

    if not usernames:
        return StageResult(
            stage=stage,
            status="skipped",
            details={"reason": "no_usernames_configured"},
        )

    start = time.monotonic()
    try:
        from hiker_ingestion.client import HikerClient
        from hiker_ingestion.db import DatabaseClient as HikerDBClient
        from hiker_ingestion.orchestrator import IngestionOrchestrator

        hiker_client = HikerClient()
        hiker_db = HikerDBClient(settings.database_url)
        await hiker_db.connect()

        orchestrator = IngestionOrchestrator(hiker_client, hiker_db)
        ingested_accounts: list[str] = []

        for username in usernames:
            try:
                result = await orchestrator.ingest_creator(
                    username=username,
                    max_reels=max_reels,
                    max_comments=max_comments,
                )
                ingested_accounts.append(username)
            except Exception as exc:
                logger.error("ingestion_failed_for_user", username=username, error=str(exc))

        await hiker_db.close()
        await hiker_client.close()

        elapsed = time.monotonic() - start
        status = "success" if ingested_accounts else "failed"

        return StageResult(
            stage=stage,
            status=status,
            elapsed_sec=round(elapsed, 3),
            details={"ingested_accounts": ingested_accounts, "total": len(ingested_accounts)},
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


async def run_enrichment_stage(
    db: DatabaseClient,
    limit: int = 10,
) -> StageResult:
    stage = PipelineStage.ENRICHMENT
    start = time.monotonic()
    try:
        from app.enrichment import enrich_pending_reels

        results = await enrich_pending_reels(db, limit=limit)
        elapsed = time.monotonic() - start

        return StageResult(
            stage=stage,
            status="success",
            elapsed_sec=round(elapsed, 3),
            details={"enriched_count": len(results), "limit": limit},
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


async def run_analytics_stage(
    db: DatabaseClient,
    limit: int = 100,
) -> StageResult:
    stage = PipelineStage.ANALYTICS
    start = time.monotonic()
    try:
        from app.analytics import run_analytics_pipeline, snapshot_all_metrics

        pipeline_result = await run_analytics_pipeline(db, limit=limit)
        snap_result = await snapshot_all_metrics(db, limit=limit)

        elapsed = time.monotonic() - start

        return StageResult(
            stage=stage,
            status="success",
            elapsed_sec=round(elapsed, 3),
            details={
                "analytics_processed": pipeline_result.get("processed", 0),
                "analytics_failed": pipeline_result.get("failed", 0),
                "snapshots_created": snap_result.get("snapshots_created", 0),
            },
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


async def run_intelligence_stage(
    db: DatabaseClient,
    limit: int = 100,
    use_llm: bool = True,
) -> StageResult:
    stage = PipelineStage.INTELLIGENCE
    start = time.monotonic()
    try:
        from app.content_engine import run_content_intelligence_pipeline
        from app.llm import LLMClient

        llm_client = LLMClient() if use_llm else None
        result = await run_content_intelligence_pipeline(
            db,
            limit=limit,
            use_llm=use_llm,
            llm_client=llm_client,
        )
        elapsed = time.monotonic() - start

        return StageResult(
            stage=stage,
            status="success",
            elapsed_sec=round(elapsed, 3),
            details={
                "processed": result.get("processed", 0),
                "failed": result.get("failed", 0),
            },
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


async def run_knowledge_stage(
    db: DatabaseClient,
    account_id: str = "default",
    limit: int = 200,
) -> StageResult:
    stage = PipelineStage.KNOWLEDGE
    start = time.monotonic()
    try:
        from app.creator_pipeline import run_creator_intelligence_pipeline

        result = await run_creator_intelligence_pipeline(
            db,
            account_id=account_id,
            limit=limit,
        )
        elapsed = time.monotonic() - start

        raw_status = result.get("status", "failed")
        normalized: Literal["success", "skipped", "failed"] = (
            "success" if raw_status == "completed" else raw_status
        )
        return StageResult(
            stage=stage,
            status=normalized,
            elapsed_sec=round(elapsed, 3),
            details={
                "reels_analyzed": result.get("reels_analyzed", 0),
                "profile_updated": result.get("profile_updated", False),
            },
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


async def run_agent_stage(
    db: DatabaseClient,
) -> StageResult:
    stage = PipelineStage.AGENT
    start = time.monotonic()
    try:
        from app.graph.graph import compiled_graph

        g = compiled_graph.get_graph()
        node_count = len(g.nodes)

        elapsed = time.monotonic() - start

        return StageResult(
            stage=stage,
            status="success",
            elapsed_sec=round(elapsed, 3),
            details={"node_count": node_count, "graph_compiled": True},
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


async def run_retrieval_stage(
    db: DatabaseClient,
) -> StageResult:
    stage = PipelineStage.RETRIEVAL
    start = time.monotonic()
    try:
        from app.reranker import (
            RERANKER_TOP_K,
            compute_retrieval_confidence,
            merge_and_dedup_candidates,
            rerank_candidates,
            select_top_k,
        )

        candidates = [
            {"source": "hybrid_search", "data": {"reel_id": "r1", "retrieval_score": 0.85, "caption": "test reel content for retrieval verification", "contexts": ["test context"]}},
            {"source": "hybrid_search", "data": {"reel_id": "r2", "bm25_score": 0.72, "caption": "another test reel with different content", "contexts": ["more context"]}},
        ]

        merged = merge_and_dedup_candidates(candidates)
        reranked = rerank_candidates(merged, "test reel content")
        top_k = select_top_k(reranked, k=RERANKER_TOP_K)
        confidence = compute_retrieval_confidence(top_k, "test reel content")

        elapsed = time.monotonic() - start

        return StageResult(
            stage=stage,
            status="success",
            elapsed_sec=round(elapsed, 3),
            details={
                "merged_count": len(merged),
                "reranked_count": len(reranked),
                "top_k": len(top_k),
                "confidence": confidence.get("combined_score", 0.0),
            },
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return StageResult(
            stage=stage,
            status="failed",
            elapsed_sec=round(elapsed, 3),
            error=str(exc),
        )


STAGE_RUNNERS = {
    PipelineStage.INGESTION: run_ingestion_stage,
    PipelineStage.ENRICHMENT: run_enrichment_stage,
    PipelineStage.ANALYTICS: run_analytics_stage,
    PipelineStage.INTELLIGENCE: run_intelligence_stage,
    PipelineStage.KNOWLEDGE: run_knowledge_stage,
    PipelineStage.AGENT: run_agent_stage,
    PipelineStage.RETRIEVAL: run_retrieval_stage,
}


async def run_pipeline(
    db: DatabaseClient,
    stages: list[PipelineStage] | None = None,
    ingestion_usernames: list[str] | None = None,
    ingestion_max_reels: int = DEFAULT_INGESTION_MAX_REELS,
    ingestion_max_comments: int = DEFAULT_INGESTION_MAX_COMMENTS,
    enrichment_limit: int = 10,
    analytics_limit: int = 100,
    intelligence_limit: int = 100,
    intelligence_use_llm: bool = True,
    knowledge_account_id: str = "default",
    knowledge_limit: int = 200,
) -> PipelineResult:
    run_id = str(uuid.uuid4())
    start = time.monotonic()

    if stages is None:
        stages = list(PipelineStage)

    logger.info("pipeline_started", run_id=run_id, stages=[str(s) for s in stages])

    stage_results: list[StageResult] = []
    pipeline_status: Literal["success", "partial", "failed"] = "success"

    for stage in stages:
        runner = STAGE_RUNNERS.get(stage)
        if runner is None:
            logger.warning("pipeline_stage_unknown", stage=str(stage))
            continue

        stage_start = time.monotonic()
        try:
            kwargs = _get_stage_kwargs(
                stage=stage,
                db=db,
                ingestion_usernames=ingestion_usernames,
                ingestion_max_reels=ingestion_max_reels,
                ingestion_max_comments=ingestion_max_comments,
                enrichment_limit=enrichment_limit,
                analytics_limit=analytics_limit,
                intelligence_limit=intelligence_limit,
                intelligence_use_llm=intelligence_use_llm,
                knowledge_account_id=knowledge_account_id,
                knowledge_limit=knowledge_limit,
            )
            result = await runner(**kwargs)
        except Exception as exc:
            stage_elapsed = time.monotonic() - stage_start
            result = StageResult(
                stage=stage,
                status="failed",
                elapsed_sec=round(stage_elapsed, 3),
                error=str(exc),
            )

        stage_results.append(result)
        _record_stage_metrics(result)

        if result.status == "failed":
            pipeline_status = "failed"
        elif result.status == "skipped" and pipeline_status == "success":
            pipeline_status = "partial"

    total_elapsed = time.monotonic() - start

    logger.info(
        "pipeline_completed",
        run_id=run_id,
        status=pipeline_status,
        elapsed_sec=round(total_elapsed, 3),
        stage_count=len(stage_results),
    )

    pipeline_runs_total.labels(status=pipeline_status).inc()
    pipeline_run_duration_seconds.labels(status=pipeline_status).observe(total_elapsed)
    pipeline_last_run_timestamp.labels(status=pipeline_status).set(time.time())
    pipeline_last_run_duration_seconds.labels(status=pipeline_status).set(total_elapsed)

    return PipelineResult(
        pipeline_run_id=run_id,
        status=pipeline_status,
        stages=stage_results,
        elapsed_sec=round(total_elapsed, 3),
    )


def _get_stage_kwargs(
    stage: PipelineStage,
    db: DatabaseClient,
    **kwargs: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {"db": db}

    if stage == PipelineStage.INGESTION:
        base["usernames"] = kwargs.get("ingestion_usernames")
        base["max_reels"] = kwargs.get("ingestion_max_reels", DEFAULT_INGESTION_MAX_REELS)
        base["max_comments"] = kwargs.get("ingestion_max_comments", DEFAULT_INGESTION_MAX_COMMENTS)
    elif stage == PipelineStage.ENRICHMENT:
        base["limit"] = kwargs.get("enrichment_limit", 10)
    elif stage == PipelineStage.ANALYTICS:
        base["limit"] = kwargs.get("analytics_limit", 100)
    elif stage == PipelineStage.INTELLIGENCE:
        base["limit"] = kwargs.get("intelligence_limit", 100)
        base["use_llm"] = kwargs.get("intelligence_use_llm", True)
    elif stage == PipelineStage.KNOWLEDGE:
        base["account_id"] = kwargs.get("knowledge_account_id", "default")
        base["limit"] = kwargs.get("knowledge_limit", 200)

    return base


def _record_stage_metrics(result: StageResult) -> None:
    pipeline_stage_status.labels(
        stage=str(result.stage),
        status=result.status,
    ).set(1 if result.status == "success" else 0)

    if result.status == "failed":
        pipeline_stage_errors_total.labels(stage=str(result.stage)).inc()

    pipeline_stage_duration_seconds.labels(
        stage=str(result.stage),
        status=result.status,
    ).observe(result.elapsed_sec)
