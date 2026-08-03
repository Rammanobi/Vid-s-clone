from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.pipeline import (
    PipelineResult,
    PipelineStage,
    StageResult,
    run_analytics_stage,
    run_agent_stage,
    run_enrichment_stage,
    run_intelligence_stage,
    run_knowledge_stage,
    run_pipeline,
    run_retrieval_stage,
)

pytestmark = pytest.mark.asyncio


class TestPipelineStages:
    async def test_ingestion_stage_skipped_no_usernames(self) -> None:
        db = AsyncMock()
        from app.pipeline import run_ingestion_stage

        result = await run_ingestion_stage(db, usernames=[])
        assert result.status == "skipped"
        assert result.error is None

    async def test_ingestion_stage_failed(self) -> None:
        db = AsyncMock()
        from app.pipeline import run_ingestion_stage
        from hiker_ingestion.client import HikerNotFoundError

        # run_ingestion_stage constructs a real hiker_ingestion.client.HikerClient
        # internally (it isn't injected), so without mocking it a "failure" test
        # like this one would silently make a live call to the real Hiker API
        # (confirmed: it used to ingest "test_user" and eat a real 404). Patch the
        # class itself so construction raises the same error HikerClient raises
        # for a real 404, which drives run_ingestion_stage into its top-level
        # except block (the stage's failure-handling path) deterministically and
        # with zero network I/O.
        with patch(
            "hiker_ingestion.client.HikerClient",
            side_effect=HikerNotFoundError(
                '{"detail":"Entries not found","exc_type":"NotFoundError"}'
            ),
        ):
            result = await run_ingestion_stage(db, usernames=["test_user"])

        assert result.status == "failed"
        assert result.error is not None
        assert "Entries not found" in result.error

    async def test_enrichment_stage_success(self) -> None:
        db = AsyncMock()
        with patch("app.enrichment.enrich_pending_reels", AsyncMock(return_value=[{"reel_id": "r1"}])):
            result = await run_enrichment_stage(db, limit=10)
        assert result.status == "success"
        assert result.details is not None
        assert result.details["enriched_count"] == 1

    async def test_enrichment_stage_failed(self) -> None:
        db = AsyncMock()
        with patch("app.enrichment.enrich_pending_reels", AsyncMock(side_effect=Exception("enrichment failed"))):
            result = await run_enrichment_stage(db, limit=10)
        assert result.status == "failed"
        assert "enrichment failed" in (result.error or "")

    async def test_analytics_stage_success(self) -> None:
        db = AsyncMock()
        with (
            patch("app.analytics.run_analytics_pipeline", AsyncMock(return_value={"processed": 5, "failed": 0})),
            patch("app.analytics.snapshot_all_metrics", AsyncMock(return_value={"snapshots_created": 10})),
        ):
            result = await run_analytics_stage(db, limit=100)
        assert result.status == "success"
        assert result.details is not None
        assert result.details["analytics_processed"] == 5
        assert result.details["snapshots_created"] == 10

    async def test_analytics_stage_failed(self) -> None:
        db = AsyncMock()
        with patch("app.analytics.run_analytics_pipeline", AsyncMock(side_effect=Exception("analytics failed"))):
            result = await run_analytics_stage(db, limit=100)
        assert result.status == "failed"

    async def test_intelligence_stage_success(self) -> None:
        db = AsyncMock()
        with (
            patch("app.content_engine.run_content_intelligence_pipeline", AsyncMock(return_value={"processed": 3, "failed": 0})),
            patch("app.llm.LLMClient"),
        ):
            result = await run_intelligence_stage(db, limit=100, use_llm=False)
        assert result.status == "success"
        assert result.details is not None
        assert result.details["processed"] == 3

    async def test_intelligence_stage_failed(self) -> None:
        db = AsyncMock()
        with patch("app.content_engine.run_content_intelligence_pipeline", AsyncMock(side_effect=Exception("intel failed"))):
            result = await run_intelligence_stage(db, limit=100, use_llm=False)
        assert result.status == "failed"

    async def test_knowledge_stage_success(self) -> None:
        db = AsyncMock()
        with patch(
            "app.creator_pipeline.run_creator_intelligence_pipeline",
            AsyncMock(return_value={"status": "completed", "reels_analyzed": 10, "profile_updated": True}),
        ):
            result = await run_knowledge_stage(db, account_id="default", limit=200)
        assert result.status == "success"
        assert result.details is not None
        assert result.details["reels_analyzed"] == 10
        assert result.details["profile_updated"] is True

    async def test_knowledge_stage_failed(self) -> None:
        db = AsyncMock()
        with patch("app.creator_pipeline.run_creator_intelligence_pipeline", AsyncMock(side_effect=Exception("knowledge failed"))):
            result = await run_knowledge_stage(db, account_id="default", limit=200)
        assert result.status == "failed"

    async def test_agent_stage_success(self) -> None:
        db = AsyncMock()
        with patch("app.graph.graph.compiled_graph") as mock:
            mock.get_graph = lambda: type("obj", (object,), {"nodes": {"a": 1, "b": 2}})()
            result = await run_agent_stage(db)
        assert result.status == "success"
        assert result.details is not None
        assert result.details["graph_compiled"] is True

    async def test_agent_stage_failed(self) -> None:
        db = AsyncMock()
        with patch("app.graph.graph.compiled_graph") as mock:
            mock.get_graph = lambda: (_ for _ in ()).throw(Exception("graph error"))
            result = await run_agent_stage(db)
        assert result.status == "failed"

    async def test_retrieval_stage_success(self) -> None:
        db = AsyncMock()
        result = await run_retrieval_stage(db)
        assert result.status == "success"
        assert result.details is not None
        assert result.details["merged_count"] == 2
        assert result.details["reranked_count"] == 2
        assert result.details["top_k"] > 0
        assert result.details["confidence"] >= 0.0

    async def test_retrieval_stage_failed(self) -> None:
        db = AsyncMock()
        with patch("app.reranker.merge_and_dedup_candidates", side_effect=Exception("retrieval failed")):
            result = await run_retrieval_stage(db)
        assert result.status == "failed"


class TestPipelineOrchestrator:
    async def test_run_pipeline_all_stages(self) -> None:
        db = AsyncMock()
        with (
            patch("app.enrichment.enrich_pending_reels", AsyncMock(return_value=[])),
            patch("app.analytics.run_analytics_pipeline", AsyncMock(return_value={"processed": 0, "failed": 0})),
            patch("app.analytics.snapshot_all_metrics", AsyncMock(return_value={"snapshots_created": 0})),
            patch("app.content_engine.run_content_intelligence_pipeline", AsyncMock(return_value={"processed": 0, "failed": 0})),
            patch("app.creator_pipeline.run_creator_intelligence_pipeline", AsyncMock(return_value={"status": "completed", "reels_analyzed": 0, "profile_updated": False})),
            patch("app.graph.graph.compiled_graph") as mock_graph,
            patch("app.llm.LLMClient"),
        ):
            mock_graph.get_graph = lambda: type("obj", (object,), {"nodes": {"a": 1}})()
            result = await run_pipeline(
                db,
                stages=[
                    PipelineStage.ENRICHMENT,
                    PipelineStage.ANALYTICS,
                    PipelineStage.INTELLIGENCE,
                    PipelineStage.KNOWLEDGE,
                    PipelineStage.AGENT,
                    PipelineStage.RETRIEVAL,
                ],
                intelligence_use_llm=False,
            )
        assert isinstance(result, PipelineResult)
        assert result.pipeline_run_id is not None
        assert result.status in ("success", "partial")
        assert len(result.stages) == 6
        for s in result.stages:
            assert isinstance(s, StageResult)
            assert s.status in ("success", "skipped", "failed")

    async def test_run_pipeline_with_some_failures(self) -> None:
        db = AsyncMock()
        with (
            patch("app.enrichment.enrich_pending_reels", AsyncMock(side_effect=Exception("fail"))),
            patch("app.graph.graph.compiled_graph") as mock_graph,
        ):
            mock_graph.get_graph = lambda: type("obj", (object,), {"nodes": {"a": 1}})()
            result = await run_pipeline(
                db,
                stages=[PipelineStage.ENRICHMENT, PipelineStage.AGENT, PipelineStage.RETRIEVAL],
                intelligence_use_llm=False,
            )
        assert result.status == "failed"
        assert result.stages[0].status == "failed"

    async def test_run_pipeline_empty_stages(self) -> None:
        db = AsyncMock()
        result = await run_pipeline(db, stages=[])
        assert result.status == "success"
        assert len(result.stages) == 0


class TestStageResultModel:
    def test_stage_result_creation(self) -> None:
        result = StageResult(
            stage=PipelineStage.INGESTION,
            status="success",
            elapsed_sec=1.5,
            details={"count": 5},
        )
        assert result.stage == PipelineStage.INGESTION
        assert result.status == "success"
        assert result.elapsed_sec == 1.5
        assert result.details == {"count": 5}

    def test_pipeline_result_creation(self) -> None:
        stage = StageResult(stage=PipelineStage.ENRICHMENT, status="success")
        result = PipelineResult(
            pipeline_run_id="test-123",
            status="success",
            stages=[stage],
            elapsed_sec=10.0,
        )
        assert result.pipeline_run_id == "test-123"
        assert result.status == "success"
        assert len(result.stages) == 1


class TestPipelineScheduler:
    async def test_pipeline_update_loop_success(self) -> None:
        db = AsyncMock()
        import app.scheduler as sched_mod

        with (
            patch.object(sched_mod, "_run_scheduled_pipeline", AsyncMock(return_value={"status": "success", "pipeline_run_id": "p1", "elapsed_sec": 0.5, "stage_count": 4})),
            patch.object(sched_mod, "pipeline_scheduler_consecutive_failures"),
            patch.object(sched_mod, "settings") as mock_settings,
        ):
            mock_settings.creator_update_interval_hours = 0.00001

            from app.scheduler import pipeline_update_loop

            with pytest.raises(TimeoutError):
                async def run_with_timeout() -> None:
                    import asyncio

                    task = asyncio.create_task(pipeline_update_loop(db))
                    await asyncio.sleep(0.1)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        raise TimeoutError()

                await run_with_timeout()
            from app.scheduler import get_pipeline_consecutive_failures

            assert get_pipeline_consecutive_failures() == 0

    async def test_pipeline_update_loop_failure_tracking(self) -> None:
        db = AsyncMock()
        import app.scheduler as sched_mod

        with (
            patch.object(sched_mod, "_run_scheduled_pipeline", AsyncMock(return_value={"status": "failed", "pipeline_run_id": "p1", "elapsed_sec": 0.5, "stage_count": 4})),
            patch.object(sched_mod, "pipeline_scheduler_consecutive_failures"),
            patch.object(sched_mod, "settings") as mock_settings,
        ):
            mock_settings.creator_update_interval_hours = 0.00001

            from app.scheduler import pipeline_update_loop

            with pytest.raises(TimeoutError):
                async def run_with_timeout() -> None:
                    import asyncio

                    task = asyncio.create_task(pipeline_update_loop(db))
                    await asyncio.sleep(0.1)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        raise TimeoutError()

                await run_with_timeout()
            from app.scheduler import get_pipeline_consecutive_failures

            assert get_pipeline_consecutive_failures() > 0
