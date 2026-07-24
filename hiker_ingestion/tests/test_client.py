from __future__ import annotations

import pytest
import httpx

from hiker_ingestion.client import (
    HikerClient,
    HikerAuthError,
    HikerNotFoundError,
    HikerRateLimitError,
)


@pytest.fixture
def client() -> HikerClient:
    return HikerClient(
        token="test-token",
        base_url="https://api.hikerapi.com",
    )


class TestHikerClientAuth:
    def test_missing_token_raises_error(self) -> None:
        with pytest.raises(HikerAuthError, match="HIKER_API_TOKEN"):
            HikerClient(token="")


class TestHikerClientErrorMapping:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, client: HikerClient, respx_mock) -> None:
        respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=test"
        ).respond(401, json={"state": False, "error": "Token is invalid"})

        with pytest.raises(HikerAuthError):
            await client.fetch_user_by_username("test")

    @pytest.mark.asyncio
    async def test_404_raises_not_found(self, client: HikerClient, respx_mock) -> None:
        respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=nonexistent"
        ).respond(404, json={"state": False, "error": "User not found"})

        with pytest.raises(HikerNotFoundError):
            await client.fetch_user_by_username("nonexistent")

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self, client: HikerClient, respx_mock) -> None:
        respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=ratelimited"
        ).respond(429, headers={"Retry-After": "5"}, json={"error": "Rate limited"})

        with pytest.raises(HikerRateLimitError):
            await client.fetch_user_by_username("ratelimited")


class TestHikerClientSuccessfulRequests:
    @pytest.mark.asyncio
    async def test_fetch_user_by_username(self, client: HikerClient, respx_mock) -> None:
        expected = {
            "pk": "12345",
            "username": "testuser",
            "follower_count": 1000,
            "following_count": 200,
            "media_count": 50,
        }
        respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=testuser"
        ).respond(200, json=expected)

        result = await client.fetch_user_by_username("testuser")
        assert result == expected

    @pytest.mark.asyncio
    async def test_fetch_user_clips(self, client: HikerClient, respx_mock) -> None:
        expected = {
            "items": [
                {"pk": "clip1", "video_url": "https://example.com/1"},
                {"pk": "clip2", "video_url": "https://example.com/2"},
            ],
            "max_id": None,
        }
        respx_mock.get(
            "https://api.hikerapi.com/v1/user/clips/chunk?user_id=12345"
        ).respond(200, json=expected)

        result = await client.fetch_user_clips("12345")
        assert result == expected

    @pytest.mark.asyncio
    async def test_fetch_user_clips_with_pagination(
        self, client: HikerClient, respx_mock
    ) -> None:
        expected = {"items": [], "max_id": "cursor123"}
        respx_mock.get(
            "https://api.hikerapi.com/v1/user/clips/chunk?user_id=12345&max_id=cursor123"
        ).respond(200, json=expected)

        result = await client.fetch_user_clips("12345", max_id="cursor123")
        assert result == expected


class TestHikerClientRetry:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client: HikerClient, respx_mock) -> None:
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=flaky"
        )
        route.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.Response(200, json={"pk": "123", "username": "flaky"}),
        ]

        result = await client.fetch_user_by_username("flaky")
        assert result["username"] == "flaky"
        assert route.call_count == 2