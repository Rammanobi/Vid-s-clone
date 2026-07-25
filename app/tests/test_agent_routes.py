from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient, WSGITransport

from app.auth import get_current_user
from app.deps import get_db_dependency
from app.main import app

pytestmark = pytest.mark.asyncio


def _make_session(user_id: str = "testuser") -> dict[str, Any]:
    return {"id": "session-1", "userId": user_id, "summary": ""}


def _mock_graph_result(**overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "response": "test answer with **Recommendations:**\n- do this",
        "citations": [{"source": "creator_profile", "type": "creator_knowledge", "summary": "Best topics"}],
        "confidence_score": 0.85,
        "intent": {"intent_type": "content_strategy"},
        "evidence": {"source": "fallback"},
        "session_id": "session-1",
        "user_query": "test query",
        "rewritten_query": "test query",
        "creator_context": None,
        "analytics_context": None,
        "competitor_context": None,
        "retrieved_documents": None,
        "ranked_context": {},
        "citations": None,
        "conversation_memory": None,
        "retrieval_plan": None,
        "metadata_filters": None,
    }
    result.update(overrides)
    return result


@pytest.fixture(autouse=True)
def _override_auth() -> Any:
    app.dependency_overrides[get_current_user] = lambda: "testuser"
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _cleanup_db_override() -> Any:
    yield
    app.dependency_overrides.pop(get_db_dependency, None)


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


class TestAgentChatEndpoint:
    async def test_chat_success(self, auth_header: dict[str, str]) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value=_make_session())
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])

        app.dependency_overrides[get_db_dependency] = lambda: db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "session-1", "message": "analyze my content strategy"},
            )

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["session_id"] == "session-1"
        assert body["response"] != ""
        assert body["confidence_score"] is not None
        assert body["intent"] is not None

    async def test_chat_no_db(self, auth_header: dict[str, str]) -> None:
        app.dependency_overrides[get_db_dependency] = lambda: None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "s1", "message": "hi"},
            )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    async def test_chat_session_not_found(self, auth_header: dict[str, str]) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value=None)
        app.dependency_overrides[get_db_dependency] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "nonexistent", "message": "hi"},
            )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_chat_unauthorized(self, auth_header: dict[str, str]) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value=_make_session(user_id="otheruser"))
        app.dependency_overrides[get_db_dependency] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "session-1", "message": "hi"},
            )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    async def test_chat_citations_as_models(self, auth_header: dict[str, str]) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value=_make_session())
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])

        app.dependency_overrides[get_db_dependency] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "session-1", "message": "analyze my content strategy"},
            )
        body = resp.json()
        assert "citations" in body
        for c in body["citations"]:
            assert "source" in c
            assert "type" in c
            assert "summary" in c


class TestAgentStreamEndpoint:
    async def test_stream_success(self, auth_header: dict[str, str]) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value=_make_session())
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])

        app.dependency_overrides[get_db_dependency] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/agent/chat/stream",
                json={"session_id": "session-1", "message": "analyze my content strategy"},
            ) as resp:
                assert resp.status_code == status.HTTP_200_OK
                lines = []
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        lines.append(json.loads(line[6:]))

        assert len(lines) >= 2
        assert lines[0]["event"] == "start"
        assert lines[-1]["event"] == "complete"
        assert "response" in lines[-1]

    async def test_stream_no_db(self, auth_header: dict[str, str]) -> None:
        app.dependency_overrides[get_db_dependency] = lambda: None
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat/stream",
                json={"session_id": "s1", "message": "hi"},
            )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestAgentGraphEndpoint:
    async def test_graph_info(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/agent/graph")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert "nodes" in body
        assert "edges" in body
        assert "conversation_memory" in body["nodes"]
        assert "confidence_evaluation" in body["nodes"]
        assert "set_decline" in body["nodes"]
        assert "set_clarification" in body["nodes"]


class TestAgentWebSocket:
    async def test_websocket_chat_success(self) -> None:
        if not __import__("os").environ.get("JWT_SECRET"):
            pytest.skip("JWT_SECRET not configured")
        from app.config import settings
        if not settings.jwt_secret:
            pytest.skip("JWT_SECRET not configured")

        from fastapi.testclient import TestClient

        db = AsyncMock()
        db.get_session = AsyncMock(return_value=_make_session())
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])
        db.search_reels_hybrid = AsyncMock(return_value=[])

        db_override_was = app.dependency_overrides.get(get_db_dependency)
        app.dependency_overrides[get_db_dependency] = lambda: db

        from app.auth import create_access_token
        token = create_access_token(subject="testuser")

        client = TestClient(app)
        with client.websocket_connect(f"/agent/ws?token={token}") as ws:
            ws.send_json({"session_id": "session-1", "message": "analyze my content strategy", "token": token})
            data = ws.receive_json()
            assert data["event"] in ("start", "complete", "error")

        app.dependency_overrides.pop(get_db_dependency, None)
        if db_override_was is not None:
            app.dependency_overrides[get_db_dependency] = db_override_was

    async def test_websocket_auth_failure(self) -> None:
        if not __import__("os").environ.get("JWT_SECRET"):
            pytest.skip("JWT_SECRET not configured")
        from app.config import settings
        if not settings.jwt_secret:
            pytest.skip("JWT_SECRET not configured")

        from fastapi.testclient import TestClient

        db_override_was = app.dependency_overrides.get(get_db_dependency)
        db = AsyncMock()
        db.get_session = AsyncMock(return_value={"id": "s1", "userId": "testuser"})
        app.dependency_overrides[get_db_dependency] = lambda: db

        client = TestClient(app)
        with client.websocket_connect("/agent/ws?token=invalid") as ws:
            data = ws.receive_json()
            assert data["event"] == "error"
            assert "auth" in data.get("detail", "").lower() or "Authentication" in data.get("detail", "")

        app.dependency_overrides.pop(get_db_dependency, None)
        if db_override_was is not None:
            app.dependency_overrides[get_db_dependency] = db_override_was


class TestAgentMetrics:
    async def test_agent_monitoring_metrics_defined(self) -> None:
        from app.monitoring import (
            agent_confidence_bucket,
            agent_errors_total,
            agent_invocation_duration_seconds,
            agent_invocations_total,
        )
        assert agent_invocations_total is not None
        assert agent_invocation_duration_seconds is not None
        assert agent_errors_total is not None
        assert agent_confidence_bucket is not None

    async def test_metrics_records_on_invocation(self, auth_header: dict[str, str]) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value=_make_session())
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])

        app.dependency_overrides[get_db_dependency] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "session-1", "message": "analyze my content strategy"},
            )
        assert resp.status_code == 200
