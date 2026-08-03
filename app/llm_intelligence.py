from __future__ import annotations


from app.intelligence import extract_intelligence
from app.llm import LLMClient
from app.logging_setup import get_logger
from app.prompts import get_content_intelligence_prompt
from app.schema_validator import ContentIntelligenceSchema

logger = get_logger(__name__)

PARTIAL_INPUT_THRESHOLD = 2


def get_input_availability(
    transcript: str | None = None,
    caption: str | None = None,
    text_overlays: list[str] | None = None,
    visual_topics: list[str] | None = None,
    visual_summary: str | None = None,
) -> dict[str, bool]:
    return {
        "transcript": bool(transcript and transcript.strip()),
        "caption": bool(caption and caption.strip()),
        "text_overlays": bool(text_overlays and any(t.strip() for t in text_overlays)),
        "visual_topics": bool(visual_topics and len(visual_topics) > 0),
        "visual_summary": bool(visual_summary and visual_summary.strip()),
    }


def is_input_partial(
    transcript: str | None = None,
    caption: str | None = None,
    text_overlays: list[str] | None = None,
    visual_topics: list[str] | None = None,
    visual_summary: str | None = None,
) -> bool:
    available = get_input_availability(
        transcript, caption, text_overlays, visual_topics, visual_summary
    )
    present_count = sum(1 for v in available.values() if v)
    return present_count < PARTIAL_INPUT_THRESHOLD


async def extract_intelligence_with_llm(
    reel_db_id: str,
    transcript: str | None = None,
    caption: str | None = None,
    text_overlays: list[str] | None = None,
    visual_topics: list[str] | None = None,
    visual_summary: str | None = None,
    llm_client: LLMClient | None = None,
) -> ContentIntelligenceSchema:
    client = llm_client or LLMClient()

    parts: list[str] = []
    if transcript and transcript.strip():
        parts.append(f"TRANSCRIPT:\n{transcript[:3000]}")
    if caption and caption.strip():
        parts.append(f"CAPTION:\n{caption[:1000]}")
    if text_overlays:
        clean_overlays = [t.strip() for t in text_overlays if t.strip()]
        if clean_overlays:
            parts.append(f"TEXT OVERLAYS:\n{' '.join(clean_overlays)[:1000]}")
    if visual_topics:
        parts.append(f"VISUAL TOPICS:\n{', '.join(visual_topics)}")
    if visual_summary and visual_summary.strip():
        parts.append(f"VISUAL SUMMARY:\n{visual_summary[:500]}")

    input_available = get_input_availability(
        transcript, caption, text_overlays, visual_topics, visual_summary
    )

    if not parts:
        logger.warning("llm_intelligence_no_input", reel_id=reel_db_id)
        return ContentIntelligenceSchema(reel_id=reel_db_id)

    user_prompt = "\n\n".join(parts)

    try:
        result = await client.extract_structured(
            system_prompt=get_content_intelligence_prompt(),
            user_prompt=user_prompt,
        )
        logger.debug(
            "llm_intelligence_extracted",
            reel_id=reel_db_id,
            topic=result.get("topic"),
            input_available=input_available,
        )
    except Exception as exc:
        logger.error(
            "llm_intelligence_failed",
            reel_id=reel_db_id,
            error=str(exc),
            input_available=input_available,
        )
        result = {}

    validated = ContentIntelligenceSchema(
        reel_id=reel_db_id,
        topic=result.get("topic"),
        hook_type=result.get("hook_type"),
        hook_text=result.get("hook_text"),
        cta=result.get("cta"),
        content_format=result.get("content_format"),
        teaching_style=result.get("teaching_style"),
        narrative_style=result.get("narrative_style"),
        audience_intent=result.get("audience_intent"),
        sentiment=result.get("sentiment"),
        visual_style=result.get("visual_style"),
    )
    return validated


async def extract_intelligence_hybrid(
    reel_db_id: str,
    transcript: str | None = None,
    caption: str | None = None,
    text_overlays: list[str] | None = None,
    visual_topics: list[str] | None = None,
    visual_summary: str | None = None,
    llm_client: LLMClient | None = None,
    use_llm: bool = True,
) -> ContentIntelligenceSchema:
    input_available = get_input_availability(
        transcript, caption, text_overlays, visual_topics, visual_summary
    )
    input_partial = sum(1 for v in input_available.values() if v) < PARTIAL_INPUT_THRESHOLD

    rule_result = extract_intelligence(
        reel_db_id=reel_db_id,
        transcript=transcript,
        caption=caption,
        text_overlays=text_overlays,
        visual_topics=visual_topics,
        visual_summary=visual_summary,
    )

    if not use_llm:
        logger.debug(
            "intelligence_hybrid_rule_only",
            reel_id=reel_db_id,
            input_partial=input_partial,
            topic=rule_result.topic,
        )
        return rule_result

    if input_partial:
        logger.warning(
            "intelligence_hybrid_partial_input",
            reel_id=reel_db_id,
            available=input_available,
        )

    try:
        llm_result = await extract_intelligence_with_llm(
            reel_db_id=reel_db_id,
            transcript=transcript,
            caption=caption,
            text_overlays=text_overlays,
            visual_topics=visual_topics,
            visual_summary=visual_summary,
            llm_client=llm_client,
        )
    except Exception as exc:
        logger.error(
            "intelligence_hybrid_llm_fallback",
            reel_id=reel_db_id,
            error=str(exc),
        )
        return rule_result

    merged = ContentIntelligenceSchema(
        reel_id=reel_db_id,
        topic=llm_result.topic or rule_result.topic,
        hook_type=llm_result.hook_type or rule_result.hook_type,
        hook_text=llm_result.hook_text or rule_result.hook_text,
        cta=llm_result.cta or rule_result.cta,
        content_format=llm_result.content_format or rule_result.content_format,
        teaching_style=llm_result.teaching_style or rule_result.teaching_style,
        narrative_style=llm_result.narrative_style or rule_result.narrative_style,
        audience_intent=llm_result.audience_intent or rule_result.audience_intent,
        sentiment=llm_result.sentiment or rule_result.sentiment,
        visual_style=llm_result.visual_style or rule_result.visual_style,
    )

    logger.debug(
        "intelligence_hybrid_merged",
        reel_id=reel_db_id,
        input_partial=input_partial,
        topic=merged.topic,
    )

    return merged