from __future__ import annotations

from prometheus_client import Counter, Histogram, start_http_server

from app.config import settings
from app.logging_setup import get_logger

logger = get_logger(__name__)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

db_queries_total = Counter(
    "db_queries_total",
    "Total database queries",
    ["operation"],
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

auth_attempts_total = Counter(
    "auth_attempts_total",
    "Total authentication attempts",
    ["result"],
)


def start_metrics_server() -> None:
    try:
        start_http_server(settings.prometheus_port)
        logger.info(
            "prometheus_metrics_server_started",
            port=settings.prometheus_port,
        )
    except OSError as exc:
        logger.warning(
            "prometheus_metrics_server_failed",
            port=settings.prometheus_port,
            error=str(exc),
        )