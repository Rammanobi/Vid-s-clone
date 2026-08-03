from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.reel_bot.config import settings


class HikerError(Exception):
    pass


class HikerAuthError(HikerError):
    pass


class HikerNotFoundError(HikerError):
    pass


class HikerInsufficientFundsError(HikerError):
    pass


class ReelBotHikerClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.token = token or settings.hiker_api_token
        self.base_url = (base_url or settings.hiker_base_url).rstrip("/")

        if not self.token:
            raise HikerAuthError(
                "REEL_BOT_HIKER_API_TOKEN is not set. "
                "Provide a token or set the environment variable."
            )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"x-access-key": self.token},
            timeout=httpx.Timeout(30.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise HikerAuthError(f"Authentication failed: {response.text}")
        if response.status_code == 404:
            raise HikerNotFoundError(f"Resource not found: {response.text}")
        if response.status_code == 402:
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
        self, method: str, path: str, max_retries: int = 3, **kwargs: Any
    ) -> dict[str, Any]:
        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, path, **kwargs)
                self._raise_for_status(response)
                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == max_retries - 1:
                    raise HikerError(f"Max retries exceeded for {path}") from exc

                wait = 2 ** attempt
                await asyncio.sleep(wait)

            except httpx.HTTPStatusError as exc:
                raise HikerError(
                    f"HTTP {exc.response.status_code} for {path}: "
                    f"{exc.response.text[:200]}"
                ) from exc

        raise HikerError(f"Max retries exceeded for {path}")

    async def fetch_user_by_username(self, username: str) -> dict[str, Any]:
        """Fetch user by username. Returns the user object from the response."""
        response = await self._request(
            "GET",
            "/v2/user/by/username",
            params={"username": username, "safe_int": "true"},
        )
        return response.get("user") or {}

    async def fetch_user_clips(
        self, user_id: str, page_id: str | None = None
    ) -> dict[str, Any]:
        """Fetch user clips with pagination."""
        params = {"user_id": user_id, "safe_int": "true"}
        if page_id:
            params["page_id"] = page_id
        return await self._request(
            "GET", "/v2/user/clips", params=params
        )

    async def fetch_user_clips_all(
        self, user_id: str, max_items: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch all user clips up to max_items."""
        items: list[dict[str, Any]] = []
        page_id: str | None = None

        while len(items) < max_items:
            data = await self.fetch_user_clips(user_id, page_id)
            chunk = data.get("response", {}).get("items", [])
            if not chunk:
                break

            for item in chunk:
                if len(items) >= max_items:
                    break
                media = item.get("media")
                if media and self._is_reel(media):
                    items.append(media)

            page_id = data.get("next_page_id")
            if not page_id:
                break

        return items[:max_items]

    @staticmethod
    def _is_reel(media: dict[str, Any]) -> bool:
        """Check if media is a reel (product_type == 'clips' and media_type == 2)."""
        return media.get("product_type") == "clips" and media.get("media_type") == 2
