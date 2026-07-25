import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # Database
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/vids_clone",
        )
    )

    # Auth / JWT
    jwt_secret: str = field(
        default_factory=lambda: os.environ.get("JWT_SECRET", "")
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(
        os.environ.get("JWT_EXPIRE_MINUTES", "60")
    )

    # Admin credentials (for token issuance)
    admin_username: str = field(
        default_factory=lambda: os.environ.get("ADMIN_USERNAME", "admin")
    )
    admin_password_hash: str = field(
        default_factory=lambda: os.environ.get("ADMIN_PASSWORD_HASH", "")
    )

    # Hiker API
    hiker_api_token: str = field(
        default_factory=lambda: os.environ.get("HIKER_API_TOKEN", "")
    )
    hiker_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "HIKER_BASE_URL", "https://api.hikerapi.com"
        )
    )

    # Server
    host: str = field(
        default_factory=lambda: os.environ.get("HOST", "0.0.0.0")
    )
    port: int = int(os.environ.get("PORT", "8000"))
    environment: str = field(
        default_factory=lambda: os.environ.get("ENVIRONMENT", "development")
    )

    # Rate limiting
    rate_limit_per_minute: int = int(
        os.environ.get("RATE_LIMIT_PER_MINUTE", "60")
    )

    # Prometheus
    prometheus_port: int = int(
        os.environ.get("PROMETHEUS_PORT", "8001")
    )

    # Modality selector thresholds
    speech_threshold: float = float(
        os.environ.get("SPEECH_THRESHOLD", "0.1")
    )
    text_threshold: float = float(
        os.environ.get("TEXT_THRESHOLD", "0.15")
    )
    visual_change_threshold: float = float(
        os.environ.get("VISUAL_CHANGE_THRESHOLD", "0.05")
    )

    # LLM / AI
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get(
            "LLM_MODEL", "gpt-4o-mini"
        )
    )
    llm_max_retries: int = int(os.environ.get("LLM_MAX_RETRIES", "3"))
    llm_timeout_sec: int = int(os.environ.get("LLM_TIMEOUT_SEC", "30"))

    # Creator intelligence update interval
    creator_update_interval_hours: int = int(
        os.environ.get("CREATOR_UPDATE_INTERVAL_HOURS", "24")
    )


settings = Settings()