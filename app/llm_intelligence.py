from __future__ import annotations

from app.intelligence import extract_intelligence
from app.llm import LLMClient
from app.logging_setup import get_logger
from app.schema_validator import ContentIntelligenceSchema

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a content analysis assistant. Analyze the given social media reel content and return a JSON object with exactly these fields (all optional, use null for unknown):

{
  "topic": "string or null (concise topic, max 100 chars)",
  "hook_type": "string or null (one of: CURIOSITY, CONTRARIAN, STORY, PROBLEM_SOLUTION, QUESTION, OTHER)",
  "hook_text": "string or null (the exact hook sentence, max 200 chars)",
  "cta": "string or null (call to action text, max 200 chars)",
  "content_format": "string or null (one of: TUTORIAL, BEHIND_THE_SCENES, TALKING_HEAD, SCREEN_RECORDING, SKIT, OTHER)",
  "teaching_style": "string or null (e.g. step_by_step, explanatory, demonstration, conversational)",
  "narrative_style": "string or null (e.g. storytelling, informational, persuasive, humorous)",
  "audience_intent": "string or null (e.g. educational, entertaining, inspiring, promotional)",
  "sentiment": "string or null (one of: positive, negative, neutral, mixed)",
  "visual_style": "string or null (e.g. outdoor, studio, text_heavy, animated, cinematic)"
}

Rules:
- hook_type must be one of the exact enum values listed above
- content_format must be one of the exact enum values listed above
- If the content is unclear for a field, use null
- Be concise
- Return ONLY valid JSON, no markdown"""


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
    if transcript:
        parts.append(f"TRANSCRIPT:\n{transcript[:3000]}")
    if caption:
        parts.append(f"CAPTION:\n{caption[:1000]}")
    if text_overlays:
        overlays_text = "; ".join(text_overlays)
        parts.append(f"TEXT OVERLAYS:\n{overlays_text[:1000]}")
    if visual_topics:
        parts.append(f"VISUAL TOPICS:\n{', '.join(visual_topics)}")
    if visual_summary:
        parts.append(f"VISUAL SUMMARY:\n{visual_summary[:500]}")
    if not parts:
        parts.append("No content available for this reel.")

    user_prompt = "\n\n".join(parts)

    try:
        result = await client.extract_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        logger.debug("llm_intelligence_extracted", reel_id=reel_db_id, topic=result.get("topic"))
    except Exception as exc:
        logger.error("llm_intelligence_failed", reel_id=reel_db_id, error=str(exc))
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
    rule_result = extract_intelligence(
        reel_db_id=reel_db_id,
        transcript=transcript,
        caption=caption,
        text_overlays=text_overlays,
        visual_topics=visual_topics,
        visual_summary=visual_summary,
    )

    if not use_llm:
        return rule_result

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
    except Exception:
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
    return merged