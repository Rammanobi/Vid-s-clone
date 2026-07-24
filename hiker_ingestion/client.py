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


class HikerRateLimitError(HikerAPIError):
    pass


class HikerAuthError(HikerAPIError):
    pass


class HikerNotFoundError(HikerAPIError):
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
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "5")
            raise HikerRateLimitError(
                f"Rate limited. Retry after {retry_after}s: {response.text}"
            )
        response.raise_for_status()

    def _get_retry_decorator(self, endpoint: str):
        return retry(
            stop=stop_after_attempt(settings.max_retries),
            wait=wait_exponential(
                multiplier=settings.min_backoff_seconds,
                min=settings.min_backoff_seconds,
                max=settings.max_backoff_seconds,
            ),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.ConnectError, HikerRateLimitError)
            ),
            before_sleep=before_sleep_log(logger, 20),
            reraise=True,
        )

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

            except (httpx.TimeoutException, httpx.ConnectError, HikerRateLimitError):
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
            f"/v2/user/by/username?username={username}",
            endpoint_label="user_by_username",
        )

    async def fetch_user_clips(
        self, user_id: str, max_id: str | None = None
    ) -> dict[str, Any]:
        path = f"/v1/user/clips/chunk?user_id={user_id}"
        if max_id:
            path += f"&max_id={max_id}"
        return await self._request(
            "GET", path, endpoint_label="user_clips"
        )

    async def fetch_user_clips_all(
        self, user_id: str, max_items: int = 100
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        max_id: str | None = None

        while len(items) < max_items:
            data = await self.fetch_user_clips(user_id, max_id)
            chunk = data.get("items", data.get("clips", []))
            if not chunk:
                break
            items.extend(chunk)
            max_id = data.get("max_id", data.get("next_page_id"))
            if not max_id:
                break

        return items[:max_items]

    async def fetch_media_comments(
        self, media_id: str, end_cursor: str | None = None
    ) -> dict[str, Any]:
        path = f"/v1/media/comments/chunk?media_id={media_id}"
        if end_cursor:
            path += f"&end_cursor={end_cursor}"
        return await self._request(
            "GET", path, endpoint_label="media_comments"
        )

    async def fetch_media_comments_all(
        self, media_id: str, max_comments: int = 500
    ) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        cursor: str | None = None

        while len(comments) < max_comments:
            data = await self.fetch_media_comments(media_id, cursor)
            chunk = data.get("items", data.get("comments", []))
            if not chunk:
                break
            comments.extend(chunk)
            cursor = data.get("end_cursor", data.get("next_page_id"))
            if not cursor:
                break

        return comments[:max_comments]

    async def fetch_media_info(self, media_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v1/media/by/id?media_id={media_id}",
            endpoint_label="media_info",
        )

    async def fetch_media_by_code(self, code: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v2/media/info/by/code?code={code}",
            endpoint_label="media_by_code",
        )