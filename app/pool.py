from __future__ import annotations

from app.config import settings
from app.logging_setup import get_logger

logger = get_logger(__name__)


def configure_pool_settings() -> dict:
    pool_settings = {
        "min_size": settings.db_pool_min_size,
        "max_size": settings.db_pool_max_size,
        "max_queries": settings.db_pool_max_queries,
        "max_inactive_connection_lifetime": settings.db_pool_max_lifetime,
    }

    logger.info(
        "connection_pool_configured",
        min_size=pool_settings["min_size"],
        max_size=pool_settings["max_size"],
        max_queries=pool_settings["max_queries"],
        max_lifetime=pool_settings["max_inactive_connection_lifetime"],
    )

    return pool_settings


NEON_POOLED_URL_HINT = """
To use Neon serverless pooling, append ?pooled=true to your DATABASE_URL:
  postgresql://user:pass@ep-example.us-east-2.aws.neon.tech/db?sslmode=require&pooled=true

Neon pooling uses PgBouncer internally to maintain a fixed number of connections,
which is ideal for serverless and high-concurrency workloads.
"""


def validate_db_url_for_neon(url: str | None = None) -> str:
    url = url or settings.database_url
    if "neon.tech" in url and "pooled=true" not in url:
        logger.warning(
            "neon_pooling_not_configured",
            hint="Append ?pooled=true to your Neon DATABASE_URL for connection pooling",
        )
    return url
