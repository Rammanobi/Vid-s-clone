from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from hiker_ingestion.config import settings
from hiker_ingestion.logging_setup import get_logger
from hiker_ingestion.monitoring import (
    api_request_duration_seconds,
    api_requests_total,
    api_retries_total,
)

logger = get_logger(__name__)


class HikerAPIError(Exception):
    pass


class HikerAuthError(HikerAPIError):
    pass


class HikerNotFoundError(HikerAPIError):
    pass


class HikerInsufficientFundsError(HikerAPIError):
    """Raised on HTTP 402 with an InsufficientFunds body. Non-retryable — the
    key's credits are exhausted, which more attempts cannot fix."""

    pass


class HikerClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.token = token or settings.hiker_api_token
        self.base_url = (base_url or settings.hiker_base_url).rstrip("/")
        self.timeout = timeout or settings.request_timeout_seconds

        if not self.token:
            raise HikerAuthError(
                "HIKER_API_TOKEN is not set. "
                "Provide a token or set the environment variable."
            )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"x-access-key": self.token},
            timeout=httpx.Timeout(self.timeout),
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise HikerAuthError(
                f"Authentication failed: {response.text}"
            )
        if response.status_code == 404:
            raise HikerNotFoundError(
                f"Resource not found: {response.text}"
            )
        if response.status_code == 402:
            # ponytail: the only confirmed HikerAPI error body shape
            # (research-endpoints.md §6) is {"exc_type": "InsufficientFunds", ...}
            try:
                body = response.json()
            except ValueError:
                body = {}
            if body.get("exc_type") == "InsufficientFunds":
                raise HikerInsufficientFundsError(
                    f"HikerAPI credits exhausted: {response.text}"
                )
        response.raise_for_status()

    async def _request(
        self, method: str, path: str, endpoint_label: str, **kwargs: Any
    ) -> dict[str, Any]:

        for attempt in range(settings.max_retries):
            try:
                start = time.monotonic()
                response = await self._client.request(method, path, **kwargs)
                duration = time.monotonic() - start

                api_request_duration_seconds.labels(
                    endpoint=endpoint_label
                ).observe(duration)

                self._raise_for_status(response)

                api_requests_total.labels(
                    endpoint=endpoint_label, status="success"
                ).inc()

                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError):
                api_requests_total.labels(
                    endpoint=endpoint_label, status="retry"
                ).inc()
                api_retries_total.labels(endpoint=endpoint_label).inc()

                if attempt == settings.max_retries - 1:
                    logger.error(
                        "hiker_api_request_failed",
                        endpoint=endpoint_label,
                        path=path,
                        attempt=attempt + 1,
                        max_retries=settings.max_retries,
                    )
                    raise

                wait = (
                    settings.min_backoff_seconds
                    * (settings.max_backoff_seconds / settings.min_backoff_seconds)
                    ** (attempt / (settings.max_retries - 1))
                )
                logger.warning(
                    "hiker_api_retrying",
                    endpoint=endpoint_label,
                    attempt=attempt + 1,
                    wait_seconds=round(wait, 2),
                )
                await asyncio.sleep(wait)

            except httpx.HTTPStatusError as exc:
                api_requests_total.labels(
                    endpoint=endpoint_label, status="error"
                ).inc()
                logger.error(
                    "hiker_api_http_error",
                    endpoint=endpoint_label,
                    status_code=exc.response.status_code,
                    response_text=exc.response.text[:500],
                )
                raise HikerAPIError(
                    f"HTTP {exc.response.status_code} for {path}: "
                    f"{exc.response.text[:200]}"
                ) from exc

        raise HikerAPIError(f"Max retries exceeded for {path}")

    async def fetch_user_by_username(
        self, username: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v2/user/by/username",
            endpoint_label="user_by_username",
            params={"username": username, "safe_int": "true"},
        )

    async def fetch_user_clips(
        self, user_id: str, page_id: str | None = None
    ) -> dict[str, Any]:
        params = {"user_id": user_id, "safe_int": "true"}
        if page_id:
            params["page_id"] = page_id
        return await self._request(
            "GET", "/v2/user/clips", endpoint_label="user_clips", params=params
        )

    async def fetch_user_clips_all(
        self, user_id: str, max_items: int = 100
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_id: str | None = None

        while len(items) < max_items:
            data = await self.fetch_user_clips(user_id, page_id)
            chunk = data.get("response", {}).get("items", [])
            if not chunk:
                break
            items.extend(chunk)
            # ponytail: next_page_id is a top-level sibling of "response", not
            # nested inside it (research-endpoints.md §4)
            page_id = data.get("next_page_id")
            if not page_id:
                break

        return items[:max_items]

    async def fetch_media_comments(
        self, media_id: str, page_id: str | None = None
    ) -> dict[str, Any]:
        # `media_id` is sent verbatim as the `id` query param. Confirmed via the
        # recorded call log (hikerapi_calls entries 5/9/13/17/21): this endpoint
        # requires the COMPOSITE "{media_pk}_{owner_pk}" form, not the plain pk.
        # The orchestrator constructs it before calling this method.
        params = {"id": media_id, "safe_int": "true"}
        if page_id:
            params["page_id"] = page_id
        return await self._request(
            "GET", "/v2/media/comments", endpoint_label="media_comments", params=params
        )

    async def fetch_media_comments_all(
        self, media_id: str, max_comments: int = 500
    ) -> list[dict[str, Any]]:
        # ponytail: first-page-only, per design non-goal — comments pagination
        # was never validated beyond page 1 (research-endpoints.md §4)
        data = await self.fetch_media_comments(media_id)
        comments = data.get("response", {}).get("comments", [])
        return comments[:max_comments]

    async def fetch_media_by_code(self, code: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v2/media/info/by/code",
            endpoint_label="media_by_code",
            params={"code": code, "safe_int": "true"},
        )
