"""LLM prompt templates, editable from Neon without a redeploy.

Precedence per prompt: DB row (table "SystemPrompt") > env var override >
built-in default. The cache is populated once at app startup and refreshed
whenever a prompt is edited through PUT /admin/prompts/{key} - no restart
needed to pick up a change. If the table is empty or unreachable, the app
still works off env vars / defaults, so this is additive, not a hard
dependency.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from app.config import settings  # noqa: F401  (ensures load_dotenv() has run)
from app.logging_setup import get_logger

if TYPE_CHECKING:
    from app.db import DatabaseClient

logger = get_logger(__name__)

_DEFAULT_INTENT_EXTRACTION = (
    "Extract structured intent from a user's query about Instagram Reels content strategy. "
    "Return JSON with keys: intent_type (one of: content_strategy, performance_analysis, "
    "recommendation, trend_discovery, competitor_analysis, general), topic (string or null), "
    "metric (string or null), time_range (string or null), comparison_type (string or null)."
)

_DEFAULT_QUERY_REWRITE = (
    "Rewrite the user's query into an optimized search query for finding relevant Instagram "
    "Reels content. Focus on factual, searchable terms. Return JSON with a single key "
    "'rewritten_query' containing the optimized query string."
)

_DEFAULT_REASONER = (
    "You are a content strategy analyst for Instagram Reels creators. Based on the evidence "
    "provided, generate a clear, actionable answer. Base your answer strictly on the evidence. "
    "If the evidence is insufficient, acknowledge limitations. Write in prose by default - use "
    "a markdown table only if the user explicitly asked for a comparison, ranking, or table, or "
    "the answer is inherently a set of per-reel numbers."
)

_DEFAULT_RECOMMENDATION = (
    "Based on the analysis and evidence, generate specific actionable recommendations for "
    "content creation strategy. Return JSON with a single key 'recommendations' containing "
    "an array of recommendation strings."
)

_DEFAULT_CONTENT_INTELLIGENCE = """You are a content analysis assistant. Analyze the given social media reel content and return a JSON object with exactly these fields (all optional, use null for unknown):

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

_DEFAULT_REEL_BOT_CHAT = """You are an AI assistant analyzing Instagram Reels performance ONLY using provided data.

CRITICAL RULES:
1. **ONLY reference data from the REEL DATA section below.** Do NOT use general knowledge or generic advice.
2. **Quote transcripts directly** when discussing content. Use exact words from the cleaned transcript.
3. **Be specific with numbers.** Reference exact views, likes, comments, shares, WPM from the data — inline in your sentences, using **bold**, unless a table is warranted by rule 6.
4. **If a reel has no transcript, explicitly state:** "Transcript not available for Reel X."
5. **Data-driven insights only.** You CAN provide tips/recommendations IF they reference specific reel performance metrics. Say "Based on Reel X having Y views..." not "typically audiences prefer...".
6. **Use a markdown table ONLY when the user asked for one.** Build a table only if the user explicitly requests a comparison, ranking, list, or table, OR the answer is inherently a set of per-reel numbers (e.g. "rank my reels by views"). For qualitative, strategic, opinion, single-reel, or "what should I do" questions, answer in prose with bolded numbers and quoted transcript snippets inline. Never use a table to hold qualitative text - a table is for numbers, not for themes, tones, or categories with example quotes. If you want to group themes with supporting quotes, use a bolded theme name followed by a nested bullet list of quotes, not a table row.
7. **Never write literal "<br>" or other HTML tags in your answer.** Use plain markdown line breaks (a blank line, or a new bullet) instead - the renderer does not interpret HTML tags as formatting.
8. **Match the shape of the question.** A one-line question gets a short answer. Do not pad a qualitative answer with metrics the user did not ask about."""

_DEFAULTS: dict[str, str] = {
    "intent_extraction": _DEFAULT_INTENT_EXTRACTION,
    "query_rewrite": _DEFAULT_QUERY_REWRITE,
    "reasoner": _DEFAULT_REASONER,
    "recommendation": _DEFAULT_RECOMMENDATION,
    "content_intelligence": _DEFAULT_CONTENT_INTELLIGENCE,
    "reel_bot_chat": _DEFAULT_REEL_BOT_CHAT,
}

_ENV_VARS: dict[str, str] = {
    "intent_extraction": "PROMPT_INTENT_EXTRACTION",
    "query_rewrite": "PROMPT_QUERY_REWRITE",
    "reasoner": "PROMPT_REASONER",
    "recommendation": "PROMPT_RECOMMENDATION",
    "content_intelligence": "PROMPT_CONTENT_INTELLIGENCE",
    "reel_bot_chat": "PROMPT_REEL_BOT_CHAT",
}

PROMPT_KEYS: tuple[str, ...] = tuple(_DEFAULTS.keys())


class PromptCache:
    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    async def refresh(self, db: "DatabaseClient") -> None:
        try:
            rows = await db.get_all_prompts()
            self._cache = {row["key"]: row["content"] for row in rows}
            logger.info("prompt_cache_refreshed", count=len(self._cache))
        except Exception as exc:
            logger.warning("prompt_cache_refresh_failed", error=str(exc))

    def get(self, key: str) -> str:
        cached = self._cache.get(key, "").strip() if key in self._cache else ""
        if cached:
            return cached
        env_value = os.environ.get(_ENV_VARS[key], "").strip()
        return env_value or _DEFAULTS[key]

    def as_dict(self) -> dict[str, Any]:
        return {
            key: {"content": self.get(key), "source": self._source(key)}
            for key in PROMPT_KEYS
        }

    def _source(self, key: str) -> str:
        if self._cache.get(key, "").strip():
            return "database"
        if os.environ.get(_ENV_VARS[key], "").strip():
            return "env"
        return "default"


prompt_cache = PromptCache()


def get_intent_extraction_prompt() -> str:
    return prompt_cache.get("intent_extraction")


def get_query_rewrite_prompt() -> str:
    return prompt_cache.get("query_rewrite")


def get_reasoner_prompt() -> str:
    return prompt_cache.get("reasoner")


def get_recommendation_prompt() -> str:
    return prompt_cache.get("recommendation")


def get_content_intelligence_prompt() -> str:
    return prompt_cache.get("content_intelligence")


def get_reel_bot_chat_prompt() -> str:
    return prompt_cache.get("reel_bot_chat")


if __name__ == "__main__":
    # ponytail: smallest check that fails if env override, DB override, or
    # fallback breaks
    assert get_intent_extraction_prompt(), "intent prompt empty"
    assert "hook_type" in get_content_intelligence_prompt(), "CI prompt truncated"

    os.environ["PROMPT_REASONER"] = "env-overridden"
    assert prompt_cache.get("reasoner") == "env-overridden", "env override failed"

    prompt_cache._cache["reasoner"] = "db-overridden"
    assert prompt_cache.get("reasoner") == "db-overridden", "db override failed"
    assert prompt_cache._source("reasoner") == "database"

    prompt_cache._cache = {}
    os.environ["PROMPT_REASONER"] = "   "
    assert prompt_cache.get("reasoner") == _DEFAULT_REASONER, "blank should fall back"

    print("prompts OK — DB override, env override, and fallback all work")
