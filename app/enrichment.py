from __future__ import annotations

from typing import Any

from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.ocr.extractor import extract_text_overlays
from app.transcription.processor import process_video

logger = get_logger(__name__)


async def enrich_reel(
    reel_db_id: str,
    instagram_reel_id: str,
    video_url: str,
    db: DatabaseClient,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reel_id": reel_db_id,
        "transcript": None,
        "text_overlays": None,
    }

    transcript_data = await process_video(video_url, instagram_reel_id)
    if transcript_data is not None:
        await db.update_reel_transcript(
            reel_db_id=reel_db_id,
            transcript=transcript_data["transcript"],
            transcript_json=transcript_data["transcript_json"],
        )
        result["transcript"] = transcript_data

    overlays = await extract_text_overlays(video_url, instagram_reel_id)
    if overlays:
        await db.update_reel_text_overlays(
            reel_db_id=reel_db_id,
            text_overlays=overlays,
        )
        result["text_overlays"] = overlays

    return result


async def enrich_pending_reels(
    db: DatabaseClient,
    limit: int = 10,
) -> list[dict[str, Any]]:
    pending = await db.get_reels_pending_enrichment(limit=limit)
    logger.info("enriching_pending_reels", count=len(pending))

    results: list[dict[str, Any]] = []
    for reel in pending:
        try:
            r = await enrich_reel(
                reel_db_id=reel["id"],
                instagram_reel_id=reel["instagramReelId"],
                video_url=reel["videoUrl"],
                db=db,
            )
            results.append(r)
        except Exception as exc:
            logger.error(
                "enrichment_failed",
                reel_id=reel["id"],
                error=str(exc),
            )

    return results