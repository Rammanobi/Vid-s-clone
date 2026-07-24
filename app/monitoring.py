from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

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

analytics_runs_total = Counter(
    "analytics_runs_total",
    "Total analytics pipeline runs",
    ["status"],
)

analytics_run_duration_seconds = Histogram(
    "analytics_run_duration_seconds",
    "Analytics pipeline run duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

analytics_errors_total = Counter(
    "analytics_errors_total",
    "Total analytics pipeline errors",
    ["error_type"],
)

analytics_last_run_timestamp = Gauge(
    "analytics_last_run_timestamp",
    "Unix timestamp of last analytics pipeline run",
)

analytics_last_run_duration_seconds = Gauge(
    "analytics_last_run_duration_seconds",
    "Duration in seconds of last analytics pipeline run",
)

analytics_reels_processed_total = Counter(
    "analytics_reels_processed_total",
    "Total reels processed by analytics pipeline",
)

llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["provider", "model", "status"],
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM API request duration in seconds",
    ["provider"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
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