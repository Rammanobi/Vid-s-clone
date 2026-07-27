from __future__ import annotations

import httpx
import pytest

import hiker_ingestion.client as client_module
from hiker_ingestion.client import (
    HikerAPIError,
    HikerAuthError,
    HikerClient,
    HikerInsufficientFundsError,
    HikerNotFoundError,
)
from hiker_ingestion.config import Settings


@pytest.fixture
def client() -> HikerClient:
    return HikerClient(
        token="test-token",
        base_url="https://api.hikerapi.com",
    )


@pytest.fixture
def fast_retry_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Swap in a Settings instance with few retries and near-zero backoff so
    transport-retry tests don't actually wait out exponential backoff."""
    test_settings = Settings(
        hiker_api_token="test-token",
        hiker_base_url="https://api.hikerapi.com",
        max_retries=3,
        min_backoff_seconds=0.001,
        max_backoff_seconds=0.002,
        request_timeout_seconds=30.0,
    )
    monkeypatch.setattr(client_module, "settings", test_settings)
    return test_settings


class TestHikerClientAuth:
    def test_missing_token_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # token="" alone falls back to settings.hiker_api_token, which may be
        # populated from a real .env in this environment, so swap in a
        # Settings instance with an empty token for a genuine
        # "no token anywhere" scenario. (Settings is a frozen dataclass, so
        # its fields can't be monkeypatched in place.)
        monkeypatch.setattr(
            client_module, "settings", Settings(hiker_api_token="")
        )
        with pytest.raises(HikerAuthError, match="HIKER_API_TOKEN"):
            HikerClient(token="")


class TestHikerClientErrorMapping:
    @pytest.mark.asyncio
    async def test_402_insufficient_funds_raises_and_is_not_retried(
        self, client: HikerClient, respx_mock
    ) -> None:
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=brokeuser&safe_int=true"
        ).respond(402, json={"exc_type": "InsufficientFunds", "detail": "no credits"})

        with pytest.raises(HikerInsufficientFundsError):
            await client.fetch_user_by_username("brokeuser")

        assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_401_raises_auth_error_and_is_not_retried(
        self, client: HikerClient, respx_mock
    ) -> None:
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=test&safe_int=true"
        ).respond(401, json={"state": False, "error": "Token is invalid"})

        with pytest.raises(HikerAuthError):
            await client.fetch_user_by_username("test")

        assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_404_raises_not_found_and_is_not_retried(
        self, client: HikerClient, respx_mock
    ) -> None:
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=nonexistent&safe_int=true"
        ).respond(404, json={"state": False, "error": "User not found"})

        with pytest.raises(HikerNotFoundError):
            await client.fetch_user_by_username("nonexistent")

        assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_402_without_insufficient_funds_body_raises_generic_error(
        self, client: HikerClient, respx_mock
    ) -> None:
        # A 402 whose body does NOT carry exc_type=InsufficientFunds falls
        # through to the generic HTTPStatusError path, not the dedicated
        # HikerInsufficientFundsError.
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=other&safe_int=true"
        ).respond(402, json={"exc_type": "SomethingElse"})

        with pytest.raises(HikerAPIError) as exc_info:
            await client.fetch_user_by_username("other")

        assert not isinstance(exc_info.value, HikerInsufficientFundsError)
        assert route.call_count == 1


class TestHikerClientNo429Handling:
    @pytest.mark.asyncio
    async def test_429_is_not_treated_as_rate_limited_or_retried(
        self, client: HikerClient, respx_mock
    ) -> None:
        # spec.md "HikerAPI error handling": no 429/Retry-After handling
        # exists. A 429 response has no special case in _raise_for_status, so
        # it falls straight through to response.raise_for_status(), which is
        # caught by the generic httpx.HTTPStatusError handler (not the
        # transport-error retry branch) and re-raised as a plain
        # HikerAPIError after exactly one attempt.
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=ratelimited&safe_int=true"
        ).respond(429, headers={"Retry-After": "5"}, json={"error": "Rate limited"})

        with pytest.raises(HikerAPIError):
            await client.fetch_user_by_username("ratelimited")

        assert route.call_count == 1


class TestHikerClientTransportRetry:
    @pytest.mark.asyncio
    async def test_connect_error_is_retried_then_succeeds(
        self, fast_retry_settings: Settings, respx_mock
    ) -> None:
        client = HikerClient(token="test-token", base_url="https://api.hikerapi.com")
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=flaky&safe_int=true"
        )
        route.side_effect = [
            httpx.ConnectError("connection refused"),
            httpx.Response(200, json={"pk": "123", "username": "flaky"}),
        ]

        result = await client.fetch_user_by_username("flaky")

        assert result["username"] == "flaky"
        assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_is_retried_then_succeeds(
        self, fast_retry_settings: Settings, respx_mock
    ) -> None:
        client = HikerClient(token="test-token", base_url="https://api.hikerapi.com")
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=slow&safe_int=true"
        )
        route.side_effect = [
            httpx.TimeoutException("timed out"),
            httpx.Response(200, json={"pk": "456", "username": "slow"}),
        ]

        result = await client.fetch_user_by_username("slow")

        assert result["username"] == "slow"
        assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_persistent_transport_error_exhausts_retries_and_raises(
        self, fast_retry_settings: Settings, respx_mock
    ) -> None:
        client = HikerClient(token="test-token", base_url="https://api.hikerapi.com")
        route = respx_mock.get(
            "https://api.hikerapi.com/v2/user/by/username?username=alwaysdown&safe_int=true"
        )
        route.side_effect = httpx.ConnectError("connection refused")

        with pytest.raises(httpx.ConnectError):
            await client.fetch_user_by_username("alwaysdown")

        assert route.call_count == fast_retry_settings.max_retries
