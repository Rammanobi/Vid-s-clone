from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_access_token
from app.deps import get_db_dependency
from app.main import app
from app.pipeline import PipelineResult
from hiker_ingestion.client import (
    HikerAuthError,
    HikerInsufficientFundsError,
    HikerNotFoundError,
)


@pytest.fixture
def admin_token() -> str:
    return create_access_token("admin")


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_account_by_username = AsyncMock(
        return_value={"id": "acct-uuid-1", "username": "okaashish"}
    )
    db.get_reels_by_account = AsyncMock(return_value=[{"id": "r1"}, {"id": "r2"}])
    app.dependency_overrides[get_db_dependency] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db_dependency, None)


async def _post(token: str, username: str = "okaashish"):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/ingest/account",
            json={"username": username},
            headers={"Authorization": f"Bearer {token}"},
        )


class TestIngestAccountSuccess:
    @pytest.mark.asyncio
    async def test_full_flow_returns_real_shape(self, admin_token, mock_db) -> None:
        with patch(
            "hiker_ingestion.orchestrator.IngestionOrchestrator.ingest_creator",
            new=AsyncMock(return_value=None),
        ), patch(
            "hiker_ingestion.db.DatabaseClient.connect", new=AsyncMock()
        ), patch(
            "hiker_ingestion.db.DatabaseClient.close", new=AsyncMock()
        ), patch(
            "hiker_ingestion.client.HikerClient.__init__", new=lambda self: None
        ), patch(
            "hiker_ingestion.client.HikerClient.close", new=AsyncMock()
        ), patch(
            "app.routes.ingest.run_pipeline",
            new=AsyncMock(
                return_value=PipelineResult(
                    pipeline_run_id="run-1", status="success", stages=[]
                )
            ),
        ):
            resp = await _post(admin_token)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["account_id"] == "acct-uuid-1"
        assert body["username"] == "okaashish"
        assert body["reels_ingested"] == 2
        assert body["pipeline_status"] == "success"

    @pytest.mark.asyncio
    async def test_strips_leading_at_symbol(self, admin_token, mock_db) -> None:
        with patch(
            "hiker_ingestion.orchestrator.IngestionOrchestrator.ingest_creator",
            new=AsyncMock(return_value=None),
        ) as mock_ingest, patch(
            "hiker_ingestion.db.DatabaseClient.connect", new=AsyncMock()
        ), patch(
            "hiker_ingestion.db.DatabaseClient.close", new=AsyncMock()
        ), patch(
            "hiker_ingestion.client.HikerClient.__init__", new=lambda self: None
        ), patch(
            "hiker_ingestion.client.HikerClient.close", new=AsyncMock()
        ), patch(
            "app.routes.ingest.run_pipeline",
            new=AsyncMock(
                return_value=PipelineResult(
                    pipeline_run_id="run-1", status="success", stages=[]
                )
            ),
        ):
            resp = await _post(admin_token, username="@okaashish")

        assert resp.status_code == 200
        assert mock_ingest.call_args.kwargs["username"] == "okaashish"


class TestIngestAccountErrors:
    @pytest.mark.asyncio
    async def test_requires_auth(self, mock_db) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/ingest/account", json={"username": "x"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_blank_username_rejected(self, admin_token, mock_db) -> None:
        resp = await _post(admin_token, username="   ")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_hiker_not_found_maps_to_404(self, admin_token, mock_db) -> None:
        with patch(
            "hiker_ingestion.orchestrator.IngestionOrchestrator.ingest_creator",
            new=AsyncMock(side_effect=HikerNotFoundError("no such user")),
        ), patch(
            "hiker_ingestion.db.DatabaseClient.connect", new=AsyncMock()
        ), patch(
            "hiker_ingestion.db.DatabaseClient.close", new=AsyncMock()
        ), patch(
            "hiker_ingestion.client.HikerClient.__init__", new=lambda self: None
        ), patch(
            "hiker_ingestion.client.HikerClient.close", new=AsyncMock()
        ):
            resp = await _post(admin_token)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hiker_auth_error_maps_to_401(self, admin_token, mock_db) -> None:
        with patch(
            "hiker_ingestion.orchestrator.IngestionOrchestrator.ingest_creator",
            new=AsyncMock(side_effect=HikerAuthError("bad key")),
        ), patch(
            "hiker_ingestion.db.DatabaseClient.connect", new=AsyncMock()
        ), patch(
            "hiker_ingestion.db.DatabaseClient.close", new=AsyncMock()
        ), patch(
            "hiker_ingestion.client.HikerClient.__init__", new=lambda self: None
        ), patch(
            "hiker_ingestion.client.HikerClient.close", new=AsyncMock()
        ):
            resp = await _post(admin_token)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_hiker_insufficient_funds_maps_to_402(self, admin_token, mock_db) -> None:
        with patch(
            "hiker_ingestion.orchestrator.IngestionOrchestrator.ingest_creator",
            new=AsyncMock(side_effect=HikerInsufficientFundsError("out of credits")),
        ), patch(
            "hiker_ingestion.db.DatabaseClient.connect", new=AsyncMock()
        ), patch(
            "hiker_ingestion.db.DatabaseClient.close", new=AsyncMock()
        ), patch(
            "hiker_ingestion.client.HikerClient.__init__", new=lambda self: None
        ), patch(
            "hiker_ingestion.client.HikerClient.close", new=AsyncMock()
        ):
            resp = await _post(admin_token)
        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_account_not_found_after_ingestion_returns_502(
        self, admin_token, mock_db
    ) -> None:
        mock_db.get_account_by_username = AsyncMock(return_value=None)
        with patch(
            "hiker_ingestion.orchestrator.IngestionOrchestrator.ingest_creator",
            new=AsyncMock(return_value=None),
        ), patch(
            "hiker_ingestion.db.DatabaseClient.connect", new=AsyncMock()
        ), patch(
            "hiker_ingestion.db.DatabaseClient.close", new=AsyncMock()
        ), patch(
            "hiker_ingestion.client.HikerClient.__init__", new=lambda self: None
        ), patch(
            "hiker_ingestion.client.HikerClient.close", new=AsyncMock()
        ):
            resp = await _post(admin_token)
        assert resp.status_code == 502


class _FakeAcquire:
    def __init__(self, conn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class TestPrimaryAccountResolution:
    @pytest.mark.asyncio
    async def test_get_primary_account_id_returns_most_recent(self) -> None:
        from app.db import DatabaseClient

        db = DatabaseClient.__new__(DatabaseClient)
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="acct-uuid-latest")
        db._pool = type("P", (), {"acquire": lambda self: _FakeAcquire(conn)})()

        result = await db.get_primary_account_id()
        assert result == "acct-uuid-latest"

    @pytest.mark.asyncio
    async def test_get_primary_account_id_none_when_empty(self) -> None:
        from app.db import DatabaseClient

        db = DatabaseClient.__new__(DatabaseClient)
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        db._pool = type("P", (), {"acquire": lambda self: _FakeAcquire(conn)})()

        result = await db.get_primary_account_id()
        assert result is None
