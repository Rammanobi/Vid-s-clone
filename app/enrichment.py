from __future__ import annotations

from pathlib import Path
from typing import Any

from app.clip.extractor import extract_visual_features
from app.config import settings
from app.db import DatabaseClient
from app.intelligence import extract_intelligence
from app.logging_setup import get_logger
from app.ocr.extractor import extract_text_overlays_with_frames
from app.selector import (
    ModalityScores,
    compute_text_score,
    compute_visual_change_score,
    decide_modalities,
)
from app.transcription.processor import process_video_with_audio

logger = get_logger(__name__)


async def enrich_reel(
    reel_db_id: str,
    instagram_reel_id: str,
    video_url: str,
    db: DatabaseClient,
    audio_bytes: bytes | None = None,
    frames: list[Any] | None = None,
    ocr_frame_texts: list[list[str]] | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reel_id": reel_db_id,
        "transcript": None,
        "text_overlays": None,
        "visual_features": None,
        "modality_decision": None,
        "content_intelligence": None,
    }

    speech_score = 0.0
    text_score = 0.0
    visual_change_score = 0.0

    if audio_bytes and len(audio_bytes) > 44:
        from app.transcription.vad import get_speech_score
        speech_score = get_speech_score(audio_bytes)

    frame_count = len(frames) if frames else 0
    if ocr_frame_texts is not None and frame_count > 0:
        text_score = compute_text_score(ocr_frame_texts, frame_count)

    if frames and len(frames) >= 2:
        visual_change_score = compute_visual_change_score(frames)

    decision = decide_modalities(
        speech_score=speech_score,
        text_score=text_score,
        visual_change_score=visual_change_score,
        speech_threshold=settings.speech_threshold,
        text_threshold=settings.text_threshold,
        visual_threshold=settings.visual_change_threshold,
    )
    result["modality_decision"] = {
        "run_transcription": decision.run_transcription,
        "run_ocr": decision.run_ocr,
        "run_clip": decision.run_clip,
        "scores": {
            "speech_score": decision.scores.speech_score,
            "text_score": decision.scores.text_score,
            "visual_change_score": decision.scores.visual_change_score,
        },
    }

    if decision.run_transcription and audio_bytes:
        transcript_data = await process_video_with_audio(
            video_url, instagram_reel_id, audio_bytes=audio_bytes
        )
        if transcript_data is not None:
            await db.update_reel_transcript(
                reel_db_id=reel_db_id,
                transcript=transcript_data["transcript"],
                transcript_json=transcript_data["transcript_json"],
            )
            result["transcript"] = transcript_data
    elif not decision.run_transcription:
        logger.debug("transcription_skipped_by_selector", reel=instagram_reel_id)

    if decision.run_ocr and frames:
        overlays = await extract_text_overlays_with_frames(
            video_url, instagram_reel_id, frames=frames
        )
        if overlays:
            await db.update_reel_text_overlays(
                reel_db_id=reel_db_id,
                text_overlays=overlays,
            )
            result["text_overlays"] = overlays
    elif not decision.run_ocr:
        logger.debug("ocr_skipped_by_selector", reel=instagram_reel_id)

    if decision.run_clip and frames:
        visual_data = await extract_visual_features(
            video_url, instagram_reel_id, frames=frames
        )
        if visual_data is not None:
            await db.update_reel_visual_features(
                reel_db_id=reel_db_id,
                embedding=visual_data["combined_embedding"],
                visual_topics=visual_data["visual_topics"],
                visual_summary=visual_data["visual_summary"],
            )
            result["visual_features"] = visual_data
    elif not decision.run_clip:
        logger.debug("clip_skipped_by_selector", reel=instagram_reel_id)

    transcript_text = (
        result["transcript"]["transcript"]
        if result["transcript"]
        else None
    )
    overlays_list = result["text_overlays"] or []
    visual_topics = (
        result["visual_features"]["visual_topics"]
        if result["visual_features"]
        else None
    )
    visual_summary = (
        result["visual_features"]["visual_summary"]
        if result["visual_features"]
        else None
    )

    intelligence = extract_intelligence(
        reel_db_id=reel_db_id,
        transcript=transcript_text,
        caption=caption,
        text_overlays=overlays_list,
        visual_topics=visual_topics,
        visual_summary=visual_summary,
    )
    await db.upsert_content_intelligence(
        reel_db_id=reel_db_id,
        topic=intelligence.topic,
        hook_type=intelligence.hook_type.value if intelligence.hook_type else None,
        hook_text=intelligence.hook_text,
        cta=intelligence.cta,
        content_format=(
            intelligence.content_format.value
            if intelligence.content_format
            else None
        ),
        teaching_style=intelligence.teaching_style,
        narrative_style=intelligence.narrative_style,
        audience_intent=intelligence.audience_intent,
        sentiment=intelligence.sentiment,
        visual_style=intelligence.visual_style,
    )
    result["content_intelligence"] = intelligence.model_dump(exclude={"reel_id"})

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