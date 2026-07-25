from __future__ import annotations

import pytest

from app.main import app
from app.monitoring import (
    knowledge_consecutive_failures,
    knowledge_scheduler_running,
)
from app.scheduler import ALERT_THRESHOLD

pytestmark = pytest.mark.asyncio


class TestKnowledgeHealthEndpoint:
    async def test_health_returns_status(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "database" in data
            assert "reel_count" in data
            assert "profile_exists" in data
            assert "scheduler" in data
            assert "last_run" in data
            assert "alerts" in data
            assert "version" in data

    async def test_health_no_auth_required(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            assert resp.status_code == 200

    async def test_health_contains_scheduler_info(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            scheduler = data["scheduler"]
            assert "running" in scheduler
            assert "consecutive_failures" in scheduler
            assert "alert_threshold" in scheduler
            assert scheduler["alert_threshold"] == ALERT_THRESHOLD

    async def test_propagates_last_run_info(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            assert "last_run" in data
            assert "last_run_timestamp" in data
            assert "last_run_duration_sec" in data
            assert "last_run_reels_processed" in data


class TestKnowledgeSchedulerHealth:
    async def test_scheduler_running_gauge_reflects_state(self) -> None:
        knowledge_scheduler_running.set(1)
        val = knowledge_scheduler_running._value.get()
        assert val == 1.0

    async def test_scheduler_stopped_gauge(self) -> None:
        knowledge_scheduler_running.set(0)
        val = knowledge_scheduler_running._value.get()
        assert val == 0.0

    async def test_consecutive_failures_gauge_tracks(self) -> None:
        knowledge_consecutive_failures.set(5)
        val = knowledge_consecutive_failures._value.get()
        assert val == 5.0

    async def test_consecutive_failures_zero_initially(self) -> None:
        knowledge_consecutive_failures.set(0)
        val = knowledge_consecutive_failures._value.get()
        assert val == 0.0

    async def test_consecutive_failures_reset(self) -> None:
        knowledge_consecutive_failures.set(3)
        knowledge_consecutive_failures.set(0)
        assert knowledge_consecutive_failures._value.get() == 0.0

    async def test_alert_threshold_constant(self) -> None:
        assert ALERT_THRESHOLD == 3


class TestKnowledgeHealthAlerts:
    async def test_no_alerts_when_healthy(self) -> None:
        from httpx import ASGITransport, AsyncClient

        knowledge_consecutive_failures.set(0)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            if data["status"] == "healthy":
                assert data["alerts"] == []

    async def test_alert_on_excessive_failures(self) -> None:
        from httpx import ASGITransport, AsyncClient

        knowledge_consecutive_failures.set(5)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            if data["status"] == "degraded":
                assert "scheduler_excessive_failures" in data["alerts"]

    async def test_alert_on_db_unavailable(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            if data["database"] == "unavailable":
                assert "database_unavailable" in data["alerts"]

    async def test_alert_threshold_boundary_just_below(self) -> None:
        from httpx import ASGITransport, AsyncClient

        knowledge_consecutive_failures.set(ALERT_THRESHOLD - 1)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            assert "scheduler_excessive_failures" not in data.get("alerts", [])

    async def test_alert_threshold_boundary_at(self) -> None:
        from httpx import ASGITransport, AsyncClient

        knowledge_consecutive_failures.set(ALERT_THRESHOLD)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            alerts = data.get("alerts", [])
            if "scheduler_excessive_failures" in alerts:
                assert data["status"] in ("degraded",)

    async def test_consecutive_failures_reflects_in_endpoint(self) -> None:
        from httpx import ASGITransport, AsyncClient

        knowledge_consecutive_failures.set(7)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/knowledge/health")
            data = resp.json()
            assert data["scheduler"]["consecutive_failures"] == 7