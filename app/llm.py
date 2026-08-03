from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from app.config import settings
from app.logging_setup import get_logger
from app.monitoring import llm_request_duration_seconds, llm_requests_total

logger = get_logger(__name__)


class LLMClientError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
        timeout_sec: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.max_retries = max_retries or settings.llm_max_retries
        self.timeout_sec = timeout_sec or settings.llm_timeout_sec

    async def chat(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            body["response_format"] = response_format

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            start = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                    resp = await client.post(url, headers=headers, json=body)
                elapsed = time.monotonic() - start
                llm_request_duration_seconds.labels(provider="openai").observe(elapsed)

                if resp.status_code == 200:
                    data = resp.json()
                    llm_requests_total.labels(
                        provider="openai", model=self.model, status="success"
                    ).inc()
                    return data

                status = resp.status_code
                llm_requests_total.labels(
                    provider="openai", model=self.model, status=f"http_{status}"
                ).inc()

                if status in (429, 500, 502, 503):
                    last_error = LLMClientError(
                        f"LLM API error (attempt {attempt + 1}): {status} - {resp.text[:200]}"
                    )
                    logger.warning(
                        "llm_retry",
                        attempt=attempt + 1,
                        status=status,
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue

                raise LLMClientError(
                    f"LLM API error: {status} - {resp.text[:200]}"
                )

            except httpx.TimeoutException:
                elapsed = time.monotonic() - start
                llm_request_duration_seconds.labels(provider="openai").observe(elapsed)
                last_error = LLMClientError(f"LLM timeout (attempt {attempt + 1})")
                logger.warning("llm_timeout", attempt=attempt + 1)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise last_error

        raise last_error or LLMClientError("LLM request failed after retries")

    async def extract_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        fmt = {"type": "json_object"} if schema else None
        data = await self.chat(messages, response_format=fmt)

        try:
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            return result
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMClientError(f"Failed to parse LLM response: {exc}") from exc