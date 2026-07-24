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


settings = Settings()