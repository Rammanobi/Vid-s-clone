from __future__ import annotations

import json
import time
from typing import Any

from app.db import DatabaseClient
from app.llm import LLMClient
from app.llm_intelligence import extract_intelligence_hybrid
from app.logging_setup import get_logger
from app.monitoring import (
    content_intelligence_reels_processed_total,
    content_intelligence_runs_total,
    content_intelligence_run_duration_seconds,
    content_intelligence_errors_total,
    content_intelligence_last_run_timestamp,
    content_intelligence_last_run_duration_seconds,
)
from app.routes.content import record_content_intelligence_run, record_content_intelligence_error

logger = get_logger(__name__)


async def process_single_reel_intelligence(
    reel: dict[str, Any],
    db: DatabaseClient,
    llm_client: LLMClient | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    reel_id: str = reel["id"]

    transcript = reel.get("transcript")
    caption = reel.get("caption")
    text_overlays = reel.get("textOverlays") or reel.get("text_overlays")
    visual_topics = reel.get("visualTopics") or reel.get("visual_topics")
    visual_summary = reel.get("visualSummary") or reel.get("visual_summary")

    intelligence = await extract_intelligence_hybrid(
        reel_db_id=reel_id,
        transcript=transcript,
        caption=caption,
        text_overlays=text_overlays,
        visual_topics=visual_topics,
        visual_summary=visual_summary,
        llm_client=llm_client,
        use_llm=use_llm,
    )

    await db.upsert_content_intelligence(
        reel_db_id=reel_id,
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

    logger.debug(
        "content_intelligence_computed",
        reel_id=reel_id,
        topic=intelligence.topic,
        hook_type=intelligence.hook_type.value if intelligence.hook_type else None,
    )

    return {
        "reel_id": reel_id,
        "topic": intelligence.topic,
        "hook_type": intelligence.hook_type.value if intelligence.hook_type else None,
        "hook_text": intelligence.hook_text,
        "cta": intelligence.cta,
        "content_format": intelligence.content_format.value if intelligence.content_format else None,
        "sentiment": intelligence.sentiment,
        "teaching_style": intelligence.teaching_style,
        "narrative_style": intelligence.narrative_style,
        "audience_intent": intelligence.audience_intent,
        "visual_style": intelligence.visual_style,
    }


async def run_content_intelligence_pipeline(
    db: DatabaseClient,
    limit: int = 100,
    offset: int = 0,
    use_llm: bool = True,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    reels = await db.get_reels_with_metrics(limit=limit, offset=offset)
    total = len(reels)
    logger.info("content_intelligence_pipeline_started", reel_count=total)

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for reel in reels:
        try:
            result = await process_single_reel_intelligence(
                reel, db, llm_client=llm_client, use_llm=use_llm
            )
            results.append(result)
            content_intelligence_reels_processed_total.inc()
        except Exception as exc:
            error_msg = f"reel {reel['id']}: {exc}"
            errors.append(error_msg)
            logger.error(
                "content_intelligence_reel_failed",
                reel_id=reel["id"],
                error=str(exc),
            )
            record_content_intelligence_error("reel_failure")

    elapsed = time.monotonic() - start
    record_content_intelligence_run(
        duration_sec=elapsed,
        reels_processed=len(results),
        status="completed" if not errors else "partial_failure",
    )
    logger.info(
        "content_intelligence_pipeline_completed",
        processed=len(results),
        failed=len(errors),
        elapsed_sec=round(elapsed, 3),
    )

    return {
        "processed": len(results),
        "failed": len(errors),
        "elapsed_sec": round(elapsed, 3),
        "results": results,
        "errors": errors,
    }


def format_intelligence_output(result: dict[str, Any]) -> str:
    output = {
        "reel_id": result.get("reel_id"),
        "topic": result.get("topic"),
        "hook_type": result.get("hook_type"),
        "hook_text": result.get("hook_text"),
        "cta": result.get("cta"),
        "content_format": result.get("content_format"),
        "sentiment": result.get("sentiment"),
        "teaching_style": result.get("teaching_style"),
        "narrative_style": result.get("narrative_style"),
        "audience_intent": result.get("audience_intent"),
        "visual_style": result.get("visual_style"),
    }
    return json.dumps(output, indent=2)