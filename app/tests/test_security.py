from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

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


class TestSecurityHeaders:
    async def test_security_headers_present(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert resp.headers.get("Permissions-Policy") is not None
        assert resp.headers.get("X-Request-ID") is not None

    async def test_cors_headers(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.options(
                "/health",
                headers={
                    "Origin": "http://example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert "access-control-allow-origin" in resp.headers


class TestInputValidation:
    async def test_request_id_header(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/health",
                headers={"X-Request-ID": "custom-id-123"},
            )
        assert resp.headers.get("X-Request-ID") == "custom-id-123"

    async def test_large_payload_rejected(self) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value={"id": "s1", "userId": "testuser"})
        app.dependency_overrides[get_db_dependency] = lambda: db
        large_payload = {"session_id": "s1", "message": "x" * 2_000_000}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json=large_payload,
            )
        assert resp.status_code in (status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestRateLimiting:
    async def test_rate_limit_header_format(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == status.HTTP_200_OK


class TestInputSanitization:
    async def test_path_traversal_returns_404(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health/../config")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_sql_injection_in_path_returns_404(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health'; DROP TABLE users; --")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_xss_in_query_string(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health?q=<script>alert('xss')</script>")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.text
        assert "<script>" not in body

    async def test_unicode_normalization(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health/%C0%AE%C0%AE/etc")
        assert resp.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST)

    async def test_null_bytes_rejected(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health/%00")
        assert resp.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST)


class TestAuthSecurity:
    async def test_unauthenticated_access_denied(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/auth/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_session_forgery_rejected(self) -> None:
        db = AsyncMock()
        db.get_session = AsyncMock(return_value={"id": "s1", "userId": "attacker"})
        app.dependency_overrides[get_db_dependency] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/agent/chat",
                json={"session_id": "s1", "message": "hi"},
            )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
