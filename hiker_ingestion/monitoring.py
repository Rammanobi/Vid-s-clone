from prometheus_client import Counter, Histogram, Gauge, start_http_server
from hiker_ingestion.config import settings
from hiker_ingestion.logging_setup import get_logger

logger = get_logger(__name__)

api_requests_total = Counter(
    "hiker_api_requests_total",
    "Total Hiker API requests made",
    ["endpoint", "status"],
)

api_request_duration_seconds = Histogram(
    "hiker_api_request_duration_seconds",
    "Hiker API request duration in seconds",
    ["endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

api_retries_total = Counter(
    "hiker_api_retries_total",
    "Total Hiker API retries",
    ["endpoint"],
)

accounts_fetched = Counter(
    "hiker_accounts_fetched_total",
    "Total accounts fetched and stored",
)

reels_fetched = Counter(
    "hiker_reels_fetched_total",
    "Total reels fetched and stored",
)

comments_fetched = Counter(
    "hiker_comments_fetched_total",
    "Total comments fetched and stored",
)

metrics_stored = Counter(
    "hiker_metrics_stored_total",
    "Total reel metrics stored",
)

db_insert_duration_seconds = Histogram(
    "hiker_db_insert_duration_seconds",
    "Database insert duration in seconds",
    ["table"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

last_successful_fetch = Gauge(
    "hiker_last_successful_fetch_timestamp_seconds",
    "Timestamp of last successful API fetch",
    ["data_type"],
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