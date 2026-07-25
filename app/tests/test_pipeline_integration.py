from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.auth import get_current_user
from app.deps import get_db_dependency
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _override_auth() -> Any:
    app.dependency_overrides[get_current_user] = lambda: "testuser"
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _cleanup_db_override() -> Any:
    yield
    app.dependency_overrides.pop(get_db_dependency, None)


class TestPipelineHealthEndpoint:
    async def test_pipeline_health_success(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/pipeline/health")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert "status" in body
        assert "stages" in body
        assert "ingestion" in body["stages"]
        assert "enrichment" in body["stages"]
        assert "analytics" in body["stages"]
        assert "intelligence" in body["stages"]
        assert "knowledge" in body["stages"]
        assert "agent" in body["stages"]
        assert "retrieval" in body["stages"]

    async def test_pipeline_stages_list(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/pipeline/stages")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert "stages" in body
        assert len(body["stages"]) == 7
        assert "description" in body


class TestPipelineRunEndpoint:
    async def test_trigger_pipeline_all_stages(self) -> None:
        from app.pipeline import PipelineStage, STAGE_RUNNERS

        db = AsyncMock()
        app.dependency_overrides[get_db_dependency] = lambda: db

        def _mock_stage(stage: str, **details: Any) -> object:
            return type("obj", (), {
                "stage": PipelineStage(stage),
                "status": "success",
                "elapsed_sec": 0.1,
                "details": details,
                "error": None,
            })()

        with patch.dict(
            STAGE_RUNNERS,
            {
                PipelineStage.ENRICHMENT: AsyncMock(return_value=_mock_stage("enrichment", enriched_count=0)),
                PipelineStage.ANALYTICS: AsyncMock(return_value=_mock_stage("analytics", analytics_processed=0, snapshots_created=0)),
                PipelineStage.INTELLIGENCE: AsyncMock(return_value=_mock_stage("intelligence", processed=0)),
                PipelineStage.KNOWLEDGE: AsyncMock(return_value=_mock_stage("knowledge", reels_analyzed=0, profile_updated=False)),
                PipelineStage.AGENT: AsyncMock(return_value=_mock_stage("agent", graph_compiled=True)),
                PipelineStage.RETRIEVAL: AsyncMock(return_value=_mock_stage("retrieval", top_k=10, confidence=0.5)),
            },
            clear=False,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/pipeline/run",
                    params={"stages": ["enrichment", "analytics", "intelligence", "knowledge", "agent", "retrieval"]},
                )
            assert resp.status_code == status.HTTP_202_ACCEPTED
            body = resp.json()
            assert "pipeline_run_id" in body
            assert body["status"] in ("success", "partial")
            stage_names = [s["name"] for s in body["stages"]]
            assert "ingestion" not in stage_names
            assert len(body["stages"]) >= 3


class TestGraphEndpoint:
    async def test_graph_info_has_all_nodes(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/agent/graph")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert "reranker" in body["nodes"]
        assert "parallel_retrieval" in body["nodes"]
        assert "context_fusion" in body["nodes"]
        assert "confidence_evaluation" in body["nodes"]
        assert "conversational_reasoner" in body["nodes"]
        assert "set_decline" in body["nodes"]
        assert "set_clarification" in body["nodes"]


class TestPipelineMetrics:
    async def test_monitoring_metrics_defined(self) -> None:
        from app.monitoring import (
            pipeline_last_run_duration_seconds,
            pipeline_last_run_timestamp,
            pipeline_run_duration_seconds,
            pipeline_runs_total,
            pipeline_scheduler_consecutive_failures,
            pipeline_scheduler_running,
            pipeline_stage_duration_seconds,
            pipeline_stage_errors_total,
            pipeline_stage_status,
        )
        assert pipeline_runs_total is not None
        assert pipeline_run_duration_seconds is not None
        assert pipeline_stage_duration_seconds is not None
        assert pipeline_stage_errors_total is not None
        assert pipeline_stage_status is not None
        assert pipeline_last_run_timestamp is not None
        assert pipeline_last_run_duration_seconds is not None
        assert pipeline_scheduler_running is not None
        assert pipeline_scheduler_consecutive_failures is not None
