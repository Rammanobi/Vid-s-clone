from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from app.auth import hash_password, create_access_token
from app.main import app


@pytest.fixture
def admin_token() -> str:
    return create_access_token("admin")


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data


@pytest.mark.asyncio
async def test_auth_token_missing_credentials() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/auth/me")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_with_token(admin_token: str) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["user"] == "admin"


@pytest.mark.asyncio
async def test_ingest_endpoint_requires_auth() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/ingest/account?instagram_id=test&username=test"
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_session_requires_auth() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/sessions")
        assert response.status_code == 401


class TestAuth:
    def test_hash_password_produces_different_hashes(self) -> None:
        h1 = hash_password("samepass")
        h2 = hash_password("samepass")
        assert h1 != h2

    def test_verify_password_correct(self) -> None:
        h = hash_password("mypassword")
        from app.auth import verify_password
        assert verify_password("mypassword", h)

    def test_verify_password_incorrect(self) -> None:
        h = hash_password("correct")
        from app.auth import verify_password
        assert not verify_password("wrong", h)

    def test_verify_password_invalid_format(self) -> None:
        from app.auth import verify_password
        assert not verify_password("pwd", "invalid-hash-format")


class TestJWT:
    def test_create_and_decode_token(self) -> None:
        token = create_access_token("testuser")
        from app.auth import decode_access_token
        payload = decode_access_token(token)
        assert payload["sub"] == "testuser"

    def test_expired_token(self) -> None:
        import jwt as pyjwt
        from app.config import settings

        from datetime import timedelta
        expired = pyjwt.encode(
            {
                "sub": "user",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        from app.auth import decode_access_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_access_token(expired)
        assert exc.value.status_code == 401