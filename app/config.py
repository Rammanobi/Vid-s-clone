import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Anchored to the repo root, not the process's CWD - load_dotenv() with no
# path searches CWD, which is wrong whenever this app is launched with a
# different working directory than the repo (e.g. uvicorn --app-dir from a
# parent folder never finds .env and silently falls back to every default).
# Must run before the class body: several fields below read os.environ at
# class-definition time, not at instantiation.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


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

    # Pipeline update interval
    pipeline_update_interval_hours: int = int(
        os.environ.get("PIPELINE_UPDATE_INTERVAL_HOURS", "12")
    )

    # Background schedulers (creator_update_loop, pipeline_update_loop). Off by
    # default: no scheduled path currently calls HikerAPI, but this is the hard
    # switch so nothing runs unattended without an explicit opt-in.
    schedulers_enabled: bool = field(
        default_factory=lambda: os.environ.get("SCHEDULERS_ENABLED", "false").lower()
        in ("1", "true", "yes")
    )

    # Redis
    redis_url: str = field(
        default_factory=lambda: os.environ.get("REDIS_URL", "")
    )

    # Database pool
    db_pool_min_size: int = int(os.environ.get("DB_POOL_MIN_SIZE", "2"))
    db_pool_max_size: int = int(os.environ.get("DB_POOL_MAX_SIZE", "20"))
    db_pool_max_queries: int = int(
        os.environ.get("DB_POOL_MAX_QUERIES", "50000")
    )
    db_pool_max_lifetime: int = int(
        os.environ.get("DB_POOL_MAX_LIFETIME", "3600")
    )

    def __post_init__(self) -> None:
        """Validate security-critical settings.

        In production, raise errors for missing credentials.
        In development, issue warnings but allow startup.
        """
        if self.environment == "production":
            errors: list[str] = []

            if not self.jwt_secret:
                errors.append(
                    "JWT_SECRET must be set in production (currently empty)"
                )
            if not self.admin_password_hash:
                errors.append(
                    "ADMIN_PASSWORD_HASH must be set in production (currently empty)"
                )

            if errors:
                raise ValueError(
                    "Production configuration errors:\n- "
                    + "\n- ".join(errors)
                )
        else:
            # Development: warn about missing secrets
            if not self.jwt_secret:
                warnings.warn(
                    "JWT_SECRET not configured - tokens will fail",
                    RuntimeWarning,
                    stacklevel=2,
                )
            if not self.admin_password_hash:
                warnings.warn(
                    "ADMIN_PASSWORD_HASH not configured - login will fail",
                    RuntimeWarning,
                    stacklevel=2,
                )


settings = Settings()