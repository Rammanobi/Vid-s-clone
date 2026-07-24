import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    hiker_api_token: str = field(
        default_factory=lambda: os.environ.get("HIKER_API_TOKEN", "")
    )
    hiker_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "HIKER_BASE_URL", "https://api.hikerapi.com"
        )
    )
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/vids_clone",
        )
    )
    max_retries: int = int(os.environ.get("HIKER_MAX_RETRIES", "5"))
    min_backoff_seconds: float = float(
        os.environ.get("HIKER_MIN_BACKOFF", "1.0")
    )
    max_backoff_seconds: float = float(
        os.environ.get("HIKER_MAX_BACKOFF", "60.0")
    )
    request_timeout_seconds: float = float(
        os.environ.get("HIKER_TIMEOUT", "30.0")
    )
    log_level: str = os.environ.get("HIKER_LOG_LEVEL", "INFO")
    prometheus_port: int = int(os.environ.get("PROMETHEUS_PORT", "8000"))


settings = Settings()