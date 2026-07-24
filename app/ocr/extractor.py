from __future__ import annotations

from pathlib import Path
from typing import Any

from app.logging_setup import get_logger
from app.ocr.media import cleanup, download_video
from app.ocr.processor import (
    deduplicate,
    merge_frame_texts,
    ocr_frame,
    sample_frames,
    tesseract_available,
)

logger = get_logger(__name__)


async def extract_text_overlays(
    video_url: str,
    instagram_reel_id: str | None = None,
) -> list[str]:
    reel_tag = instagram_reel_id or video_url[:40]
    logger.info("ocr_started", reel=reel_tag)

    if not tesseract_available():
        logger.warning("tesseract not available, skipping OCR")
        return []

    video_path: Path | None = None

    try:
        video_path = await download_video(video_url)
        frames = sample_frames(video_path)

        if not frames:
            logger.info("no_frames_sampled", reel=reel_tag)
            return []

        all_frame_texts: list[list[str]] = []
        for frame in frames:
            texts = ocr_frame(frame)
            if texts:
                all_frame_texts.append(texts)

        overlays = merge_frame_texts(all_frame_texts)

        if overlays:
            logger.info(
                "ocr_complete",
                reel=reel_tag,
                unique_texts=len(overlays),
            )
        else:
            logger.info("ocr_no_text_detected", reel=reel_tag)

        return overlays

    except Exception as exc:
        logger.error(
            "ocr_failed",
            reel=reel_tag,
            error=str(exc),
        )
        return []

    finally:
        if video_path is not None:
            cleanup([video_path])