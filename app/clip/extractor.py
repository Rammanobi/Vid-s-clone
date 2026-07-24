from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.clip.processor import (
    classify_topics,
    generate_frame_embedding,
    openclip_available,
)
from app.logging_setup import get_logger
from app.ocr.media import cleanup, download_video
from app.ocr.processor import sample_frames

logger = get_logger(__name__)


async def extract_visual_features(
    video_url: str,
    instagram_reel_id: str | None = None,
    frames: list[Any] | None = None,
) -> dict[str, Any] | None:
    reel_tag = instagram_reel_id or video_url[:40]
    logger.info("clip_started", reel=reel_tag)

    if not openclip_available():
        logger.warning("open_clip not available, skipping visual features")
        return None

    resolved_frames: list[Any] | None = frames
    video_path: Path | None = None

    try:
        if resolved_frames is None:
            video_path = await download_video(video_url)
            resolved_frames = sample_frames(video_path)

        if not resolved_frames:
            logger.info("no_frames_for_clip", reel=reel_tag)
            return None

        mid_frame = resolved_frames[len(resolved_frames) // 2]

        embedding = generate_frame_embedding(mid_frame)
        if embedding is None:
            logger.warning("embedding_generation_failed", reel=reel_tag)
            return None

        topics, summary = classify_topics(mid_frame)

        logger.info(
            "clip_complete",
            reel=reel_tag,
            topics_count=len(topics),
            summary_length=len(summary),
        )

        return {
            "combined_embedding": embedding,
            "visual_topics": topics,
            "visual_summary": summary,
        }

    except Exception as exc:
        logger.error(
            "clip_failed",
            reel=reel_tag,
            error=str(exc),
        )
        return None

    finally:
        if video_path is not None:
            cleanup([video_path])