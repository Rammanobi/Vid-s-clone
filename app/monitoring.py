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

content_intelligence_runs_total = Counter(
    "content_intelligence_runs_total",
    "Total content intelligence pipeline runs",
    ["status"],
)

content_intelligence_run_duration_seconds = Histogram(
    "content_intelligence_run_duration_seconds",
    "Content intelligence pipeline run duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

content_intelligence_errors_total = Counter(
    "content_intelligence_errors_total",
    "Total content intelligence pipeline errors",
    ["error_type"],
)

content_intelligence_last_run_timestamp = Gauge(
    "content_intelligence_last_run_timestamp",
    "Unix timestamp of last content intelligence pipeline run",
)

content_intelligence_last_run_duration_seconds = Gauge(
    "content_intelligence_last_run_duration_seconds",
    "Duration in seconds of last content intelligence pipeline run",
)

content_intelligence_reels_processed_total = Counter(
    "content_intelligence_reels_processed_total",
    "Total reels processed by content intelligence pipeline",
)

creator_intelligence_runs_total = Counter(
    "creator_intelligence_runs_total",
    "Total creator intelligence pipeline runs",
    ["status"],
)

creator_intelligence_run_duration_seconds = Histogram(
    "creator_intelligence_run_duration_seconds",
    "Creator intelligence pipeline run duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

creator_intelligence_errors_total = Counter(
    "creator_intelligence_errors_total",
    "Total creator intelligence pipeline errors",
    ["error_type"],
)

creator_intelligence_last_run_timestamp = Gauge(
    "creator_intelligence_last_run_timestamp",
    "Unix timestamp of last creator intelligence pipeline run",
)

creator_intelligence_last_run_duration_seconds = Gauge(
    "creator_intelligence_last_run_duration_seconds",
    "Duration in seconds of last creator intelligence pipeline run",
)

creator_intelligence_reels_processed_total = Counter(
    "creator_intelligence_reels_processed_total",
    "Total reels processed by creator intelligence pipeline",
)

knowledge_scheduler_running = Gauge(
    "knowledge_scheduler_running",
    "1 if the knowledge scheduler loop is active, 0 otherwise",
)

knowledge_consecutive_failures = Gauge(
    "knowledge_consecutive_failures",
    "Number of consecutive failure cycles in the knowledge scheduler",
)

agent_invocations_total = Counter(
    "agent_invocations_total",
    "Total LangGraph agent invocations",
    ["mode"],
)

agent_invocation_duration_seconds = Histogram(
    "agent_invocation_duration_seconds",
    "LangGraph agent invocation duration in seconds",
    ["mode"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

agent_errors_total = Counter(
    "agent_errors_total",
    "Total LangGraph agent invocation errors",
    ["mode"],
)

agent_confidence_bucket = Gauge(
    "agent_confidence_bucket",
    "Confidence score bucket for last agent invocation",
    ["bucket"],
)

pipeline_runs_total = Counter(
    "pipeline_runs_total",
    "Total pipeline runs",
    ["status"],
)

pipeline_run_duration_seconds = Histogram(
    "pipeline_run_duration_seconds",
    "Pipeline run duration in seconds",
    ["status"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

pipeline_stage_duration_seconds = Histogram(
    "pipeline_stage_duration_seconds",
    "Pipeline stage duration in seconds",
    ["stage", "status"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

pipeline_stage_errors_total = Counter(
    "pipeline_stage_errors_total",
    "Total pipeline stage errors",
    ["stage"],
)

pipeline_stage_status = Gauge(
    "pipeline_stage_status",
    "Pipeline stage status (1=success, 0=failed/skipped)",
    ["stage", "status"],
)

pipeline_last_run_timestamp = Gauge(
    "pipeline_last_run_timestamp",
    "Timestamp of last pipeline run",
    ["status"],
)

pipeline_last_run_duration_seconds = Gauge(
    "pipeline_last_run_duration_seconds",
    "Duration of last pipeline run in seconds",
    ["status"],
)

pipeline_scheduler_running = Gauge(
    "pipeline_scheduler_running",
    "Whether the pipeline scheduler is running (1=running, 0=stopped)",
)

pipeline_scheduler_consecutive_failures = Gauge(
    "pipeline_scheduler_consecutive_failures",
    "Consecutive pipeline scheduler failures",
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