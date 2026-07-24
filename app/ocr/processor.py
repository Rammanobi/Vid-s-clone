from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.logging_setup import get_logger

logger = get_logger(__name__)

_FRAME_SAMPLE_INTERVAL_SEC = 2.0
_OCR_CONFIDENCE_THRESHOLD = 30
_MIN_TEXT_LENGTH = 2


def _try_load_tesseract() -> Any:
    try:
        import pytesseract  # type: ignore[import-untyped]
        try:
            pytesseract.get_tesseract_version()
            logger.info("tesseract detected")
            return pytesseract
        except Exception:
            logger.warning("tesseract binary not found in PATH")
            return None
    except ImportError:
        logger.warning("pytesseract not installed")
        return None


_tesseract = _try_load_tesseract()


def tesseract_available() -> bool:
    return _tesseract is not None


def sample_frames(video_path: Path) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.error("cannot_open_video", path=str(video_path))
        return frames

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    frame_interval = int(fps * _FRAME_SAMPLE_INTERVAL_SEC)

    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if count % frame_interval == 0:
            frames.append(frame)
        count += 1

    cap.release()
    logger.debug(
        "frames_sampled",
        total_frames=count,
        sampled=len(frames),
        fps=fps,
    )
    return frames


def ocr_frame(
    frame: np.ndarray,
    lang: str = "eng",
) -> list[str]:
    if _tesseract is None:
        return []

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        data = _tesseract.image_to_data(
            thresh, lang=lang, output_type=_tesseract.Output.DICT  # type: ignore[arg-type]
        )

        texts: list[str] = []
        for i, text in enumerate(data.get("text", [])):
            conf = int(data.get("conf", [0])[i] or 0)
            cleaned = (text or "").strip()
            if conf >= _OCR_CONFIDENCE_THRESHOLD and len(cleaned) >= _MIN_TEXT_LENGTH:
                texts.append(cleaned)

        return texts

    except Exception as exc:
        logger.warning("ocr_frame_failed", error=str(exc))
        return []


def deduplicate(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for t in texts:
        normalized = t.strip().lower()
        if normalized not in seen and normalized:
            seen.add(normalized)
            result.append(t.strip())
    return result


def merge_frame_texts(all_frame_texts: list[list[str]]) -> list[str]:
    merged: list[str] = []
    for frame_texts in all_frame_texts:
        merged.extend(frame_texts)
    return deduplicate(merged)