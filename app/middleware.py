from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logging_setup import get_logger

logger = get_logger(__name__)


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call):
        if settings.environment == "production":
            forwarded = request.headers.get("X-Forwarded-Proto", "")
            if forwarded.lower() != "https":
                raise HTTPException(
                    status_code=status.HTTP_426_UPGRADE_REQUIRED,
                    detail="HTTPS required",
                )
        return await call(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call):
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        response = await call(request)
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        return response


def add_rate_limiting(app: FastAPI) -> None:
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        from slowapi.util import get_remote_address

        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[
                f"{settings.rate_limit_per_minute}/minute"
            ],
            enabled=settings.environment == "production",
        )

        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

        logger.info(
            "rate_limiting_enabled",
            limit_per_minute=settings.rate_limit_per_minute,
        )
    except ImportError:
        logger.warning("slowapi not installed; rate limiting disabled")