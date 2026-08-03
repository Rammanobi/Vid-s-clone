from __future__ import annotations

import io
import wave
from typing import Any

import numpy as np

from app.logging_setup import get_logger

logger = get_logger(__name__)

_SPEECH_PROB_THRESHOLD = 0.5
_FRAME_DURATION_MS = 30


def _try_load_silero_vad() -> Any:
    try:
        import torch  # type: ignore[import-untyped]
        silero_vad = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        return silero_vad
    except (ImportError, Exception) as exc:
        logger.warning("silero-vad not available", error=str(exc))
        return None


_vad_model = _try_load_silero_vad()


def vad_enabled() -> bool:
    return _vad_model is not None


def _read_wave(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, sample_rate


def get_speech_score(audio_bytes: bytes) -> float:
    if _vad_model is None:
        logger.info("silero-vad not loaded, assuming speech present")
        return 1.0

    if not audio_bytes or len(audio_bytes) < 44:
        return 0.0

    import torch  # type: ignore[import-untyped]

    audio, sample_rate = _read_wave(audio_bytes)
    if len(audio) == 0:
        return 0.0

    speech_frames = 0
    total_frames = 0
    frame_length = int(sample_rate * _FRAME_DURATION_MS / 1000)

    for start in range(0, len(audio), frame_length):
        chunk = audio[start : start + frame_length]
        if len(chunk) < frame_length:
            break
        try:
            prob = _vad_model(torch.from_numpy(chunk), sample_rate).item()
            if prob >= _SPEECH_PROB_THRESHOLD:
                speech_frames += 1
            total_frames += 1
        except Exception:
            continue

    if total_frames == 0:
        return 0.0

    score = speech_frames / total_frames
    logger.debug(
        "vad_complete",
        speech_frames=speech_frames,
        total_frames=total_frames,
        speech_score=round(score, 4),
    )
    return score