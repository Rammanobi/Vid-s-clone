from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.logging_setup import get_logger
from app.transcription.media import cleanup, download_video, extract_audio
from app.transcription.vad import get_speech_score
from app.transcription.whisper import transcribe, whisper_available

logger = get_logger(__name__)

_SPEECH_THRESHOLD = 0.1


async def _transcribe_from_audio_path(
    audio_path: str,
    reel_tag: str,
) -> dict[str, Any] | None:
    if not whisper_available():
        logger.warning("faster-whisper not available, skipping transcription")
        return None

    result = transcribe(audio_path)
    if result is None:
        return None

    segments_dict = [seg.model_dump() for seg in result.segments]
    return {
        "transcript": result.full_text,
        "transcript_json": segments_dict,
    }


async def process_video(
    video_url: str,
    instagram_reel_id: str | None = None,
) -> dict[str, Any] | None:
    reel_tag = instagram_reel_id or video_url[:40]
    logger.info("transcription_started", reel=reel_tag)

    video_path: Path | None = None
    audio_path: Path | None = None

    try:
        video_path = await download_video(video_url)
        audio_fd, audio_path_str = tempfile.mkstemp(suffix=".wav")
        audio_path = Path(audio_path_str)

        extract_audio(video_path, audio_path)

        return await _transcribe_from_audio_path(str(audio_path), reel_tag)

    except Exception as exc:
        logger.error(
            "transcription_failed",
            reel=reel_tag,
            error=str(exc),
        )
        return None

    finally:
        cleanup_paths = [p for p in [video_path, audio_path] if p is not None]
        cleanup(cleanup_paths)


async def process_video_with_audio(
    video_url: str,
    instagram_reel_id: str | None = None,
    audio_bytes: bytes | None = None,
) -> dict[str, Any] | None:
    reel_tag = instagram_reel_id or video_url[:40]

    if audio_bytes is None or len(audio_bytes) < 44:
        return await process_video(video_url, instagram_reel_id)

    audio_path: Path | None = None

    try:
        audio_fd, audio_path_str = tempfile.mkstemp(suffix=".wav")
        audio_path = Path(audio_path_str)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        return await _transcribe_from_audio_path(str(audio_path), reel_tag)

    except Exception as exc:
        logger.error(
            "transcription_with_audio_failed",
            reel=reel_tag,
            error=str(exc),
        )
        return None

    finally:
        if audio_path is not None:
            cleanup([audio_path])