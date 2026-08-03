from __future__ import annotations

import asyncio

import httpx

from app.reel_bot.config import settings


class LLMError(Exception):
    pass


class ReelBotLLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.timeout = timeout

        if not self.api_key:
            raise LLMError(
                "REEL_BOT_LLM_API_KEY is not set. "
                "Provide a key or set the environment variable."
            )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self.timeout),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_retries: int = 3,
    ) -> str:
        """Call the LLM and return the response text."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        for attempt in range(max_retries):
            try:
                response = await self._client.post(
                    "/chat/completions",
                    json=payload,
                )

                if response.status_code in (429, 500, 502, 503):
                    if attempt == max_retries - 1:
                        response.raise_for_status()
                    await asyncio.sleep(2 ** attempt)
                    continue

                response.raise_for_status()

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                return content

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == max_retries - 1:
                    raise LLMError("Max retries exceeded for LLM call") from exc
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as exc:
                raise LLMError(
                    f"LLM HTTP {exc.response.status_code}: {exc.response.text[:200]}"
                ) from exc

        raise LLMError("Max retries exceeded for LLM call")
