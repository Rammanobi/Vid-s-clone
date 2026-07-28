from __future__ import annotations

import uuid
from typing import Any

from app.logging_setup import get_logger
from app.transcription.models import TranscriptResult, TranscriptSegment

logger = get_logger(__name__)

_SPEECH_MIN_SCORE = 0.1

_whisper_model: Any = None
_whisper_model_loaded = False


def _try_load_whisper() -> Any:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("faster-whisper model loaded", model="base", device="cpu")
        return model
    except (ImportError, Exception) as exc:
        logger.warning("faster-whisper not available", error=str(exc))
        return None


def whisper_available() -> bool:
    global _whisper_model, _whisper_model_loaded
    if not _whisper_model_loaded:
        _whisper_model = _try_load_whisper()
        _whisper_model_loaded = True
    return _whisper_model is not None


def transcribe(audio_path: str) -> TranscriptResult | None:
    global _whisper_model, _whisper_model_loaded
    if not _whisper_model_loaded:
        _whisper_model = _try_load_whisper()
        _whisper_model_loaded = True

    if _whisper_model is None:
        logger.error("faster-whisper not loaded, cannot transcribe")
        return None

    try:
        segments, info = _whisper_model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.5,
                min_speech_duration_ms=250,
                min_silence_duration_ms=100,
            ),
        )

        seg_list: list[TranscriptSegment] = []
        text_parts: list[str] = []

        for seg in segments:
            chunk_id = str(uuid.uuid4())
            seg_list.append(
                TranscriptSegment(
                    start=round(seg.start, 2),
                    end=round(seg.end, 2),
                    text=seg.text.strip(),
                    chunk_id=chunk_id,
                )
            )
            text_parts.append(seg.text.strip())

        if not seg_list:
            logger.info("whisper_no_segments_detected")
            return None

        result = TranscriptResult(
            segments=seg_list,
            full_text=" ".join(text_parts),
            language=info.language,
        )

        logger.info(
            "transcription_complete",
            language=info.language,
            duration=info.duration,
            segments=len(seg_list),
        )
        return result

    except Exception as exc:
        logger.error("whisper_transcription_failed", error=str(exc))
        return None