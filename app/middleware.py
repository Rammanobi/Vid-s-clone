from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logging_setup import get_logger
from app.monitoring import auth_attempts_total, http_request_duration_seconds, http_requests_total

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call: Any) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call: Any) -> Response:
        request_id = getattr(request.state, "request_id", "unknown")
        start = time.monotonic()
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        try:
            response = await call(request)
            elapsed = time.monotonic() - start
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                elapsed_ms=round(elapsed * 1000, 1),
            )
            http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
            ).inc()
            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(elapsed)
            return response
        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(exc),
                elapsed_ms=round(elapsed * 1000, 1),
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call: Any) -> Response:
        response = await call(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'"
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1MB
    MAX_PATH_LENGTH = 512

    async def dispatch(self, request: Request, call: Any) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.MAX_CONTENT_LENGTH:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": f"Request body exceeds {self.MAX_CONTENT_LENGTH} bytes"},
                    )
            except ValueError:
                pass

        if request.url.path and len(str(request.url.path)) > self.MAX_PATH_LENGTH:
            return JSONResponse(
                status_code=status.HTTP_414_URI_TOO_LONG,
                content={"detail": "Request path too long"},
            )

        return await call(request)


class AuditLogMiddleware(BaseHTTPMiddleware):
    SENSITIVE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    SENSITIVE_PATHS = {"/auth/", "/session/", "/agent/chat", "/agent/ws", "/pipeline/run"}

    async def dispatch(self, request: Request, call: Any) -> Response:
        response = await call(request)
        method = request.method
        path = request.url.path

        if method in self.SENSITIVE_METHODS and any(path.startswith(sp) for sp in self.SENSITIVE_PATHS):
            request_id = getattr(request.state, "request_id", "unknown")
            logger.info(
                "audit_action",
                request_id=request_id,
                method=method,
                path=path,
                status_code=response.status_code,
                client_ip=request.client.host if request.client else None,
            )
            auth_attempts_total.labels(result="audit").inc()

        return response


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call: Any) -> Response:
        if settings.environment == "production":
            forwarded = request.headers.get("X-Forwarded-Proto", "").lower()
            if not forwarded or forwarded not in ("http", "https"):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid X-Forwarded-Proto header"},
                )
            if forwarded != "https":
                return JSONResponse(
                    status_code=status.HTTP_426_UPGRADE_REQUIRED,
                    content={"detail": "HTTPS required"},
                )
        return await call(request)


def add_rate_limiting(app: FastAPI) -> None:
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        from slowapi.util import get_remote_address

        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[f"{settings.rate_limit_per_minute}/minute"],
            enabled=settings.environment == "production",
        )

        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

        logger.info("rate_limiting_enabled", limit_per_minute=settings.rate_limit_per_minute)
    except ImportError:
        logger.warning("slowapi not installed; rate limiting disabled")


def apply_middleware(app: FastAPI) -> None:
    add_rate_limiting(app)
