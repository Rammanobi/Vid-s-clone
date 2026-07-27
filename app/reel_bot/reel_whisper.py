from __future__ import annotations

from typing import Any

from app.transcription.processor import process_video


async def transcribe_reel(
    video_url: str, instagram_reel_id: str
) -> dict[str, Any] | None:
    """Transcribe a reel's audio using local faster-whisper.

    Uses the existing app/transcription pipeline (works without Groq/OpenAI).
    Returns {"transcript": str, "transcript_json": list[dict]} or None on failure.
    """
    return await process_video(video_url, instagram_reel_id=instagram_reel_id)
