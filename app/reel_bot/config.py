from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    hiker_api_token: str = field(
        default_factory=lambda: os.environ.get("REEL_BOT_HIKER_API_TOKEN", "")
    )
    hiker_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "REEL_BOT_HIKER_BASE_URL", "https://api.hikerapi.com"
        )
    )
    llm_api_key: str = field(
        default_factory=lambda: os.environ.get("REEL_BOT_LLM_API_KEY", "")
    )
    llm_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "REEL_BOT_LLM_BASE_URL", "https://api.openai.com/v1"
        )
    )
    llm_model: str = field(
        default_factory=lambda: os.environ.get("REEL_BOT_LLM_MODEL", "gpt-4o-mini")
    )
    groq_api_key: str = field(
        default_factory=lambda: os.environ.get("GROQ_API_KEY", "")
    )
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "")
    )
    max_reels: int = field(
        default_factory=lambda: int(os.environ.get("REEL_BOT_MAX_REELS", "20"))
    )
    memory_window: int = field(
        default_factory=lambda: int(os.environ.get("REEL_BOT_MEMORY_WINDOW", "10"))
    )

    def __post_init__(self) -> None:
        if not self.hiker_api_token:
            warnings.warn(
                "REEL_BOT_HIKER_API_TOKEN is not set. Reel Bot ingestion will fail."
            )
        if not self.groq_api_key:
            warnings.warn(
                "GROQ_API_KEY is not set. Reel Bot transcription will fail."
            )
        if not self.llm_api_key:
            warnings.warn(
                "REEL_BOT_LLM_API_KEY is not set. Reel Bot chat will fail."
            )
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is not set. Cannot initialize Reel Bot."
            )


settings = Settings()
