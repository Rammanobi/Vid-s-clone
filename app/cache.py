from __future__ import annotations

import json
from typing import Any, Callable
from functools import wraps

from app.logging_setup import get_logger

logger = get_logger(__name__)

_redis_client: Any = None


def get_redis() -> Any:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        from app.config import settings

        if not settings.redis_url:
            logger.info("redis_not_configured")
            _redis_client = None
            return None

        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            max_connections=20,
        )
        logger.info("redis_connected", url=settings.redis_url)
        return _redis_client
    except Exception as exc:
        logger.warning("redis_connection_failed", error=str(exc))
        return None


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    if r is None:
        return None
    try:
        data = await r.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception as exc:
        logger.debug("cache_get_failed", key=key, error=str(exc))
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        data = json.dumps(value, default=str)
        await r.setex(key, ttl, data)
    except Exception as exc:
        logger.debug("cache_set_failed", key=key, error=str(exc))


async def cache_delete(key: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception as exc:
        logger.debug("cache_delete_failed", key=key, error=str(exc))


async def cache_delete_pattern(pattern: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.debug("cache_delete_pattern_failed", pattern=pattern, error=str(exc))


def cached(ttl: int = 300, key_prefix: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = f"{key_prefix or func.__name__}:{hash(frozenset(kwargs.items()))}"
            cached_result = await cache_get(cache_key)
            if cached_result is not None:
                return cached_result
            result = await func(*args, **kwargs)
            await cache_set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator
