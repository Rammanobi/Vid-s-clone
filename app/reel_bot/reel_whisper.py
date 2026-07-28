from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.logging_setup import get_logger
from app.reel_bot.config import settings
from app.transcription.media import cleanup, download_video, extract_audio

logger = get_logger(__name__)


async def transcribe_audio_with_groq(
    audio_path: Path, instagram_reel_id: str
) -> dict[str, Any] | None:
    """Transcribe audio using Groq's Whisper API (fast, ~2s per reel)."""
    if not settings.groq_api_key:
        logger.error("transcription_failed", reel=instagram_reel_id, error="GROQ_API_KEY not set")
        return None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": ("audio.wav", f, "audio/wav")}
                response = await client.post(
                    f"{settings.groq_base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    files=files,
                    data={"model": "whisper-large-v3-turbo"},
                )
                response.raise_for_status()
                result = response.json()
                return {"transcript": result.get("text", "")}
    except Exception as exc:
        logger.error("transcription_failed", reel=instagram_reel_id, error=str(exc))
        return None


async def transcribe_reel(
    video_url: str, instagram_reel_id: str
) -> dict[str, Any] | None:
    """Transcribe reel using Groq Whisper API: download → extract audio → Groq."""
    reel_tag = instagram_reel_id or video_url[:40]
    logger.info("transcription_started", reel=reel_tag)

    video_path: Path | None = None
    audio_path: Path | None = None

    try:
        video_path = await download_video(video_url)
        audio_fd, audio_path_str = tempfile.mkstemp(suffix=".wav")
        os.close(audio_fd)
        audio_path = Path(audio_path_str)

        extract_audio(video_path, audio_path)
        return await transcribe_audio_with_groq(audio_path, reel_tag)

    except Exception as exc:
        logger.error("transcription_failed", reel=reel_tag, error=str(exc))
        return None

    finally:
        cleanup_paths = [p for p in [video_path, audio_path] if p is not None]
        cleanup(cleanup_paths)
