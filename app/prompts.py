"""LLM prompt templates, overridable from .env.

Each prompt is read from an environment variable at import time, falling back to
the built-in default. The defaults are duplicated in .env.example so a fresh
clone works before anyone writes a .env.
"""

from __future__ import annotations

import os

from app.config import settings  # noqa: F401  (ensures load_dotenv() has run)

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
    "If the evidence is insufficient, acknowledge limitations."
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


def _prompt(env_var: str, default: str) -> str:
    value = os.environ.get(env_var, "").strip()
    return value or default


INTENT_EXTRACTION_SYSTEM_PROMPT = _prompt(
    "PROMPT_INTENT_EXTRACTION", _DEFAULT_INTENT_EXTRACTION
)
QUERY_REWRITE_SYSTEM_PROMPT = _prompt(
    "PROMPT_QUERY_REWRITE", _DEFAULT_QUERY_REWRITE
)
REASONER_SYSTEM_PROMPT = _prompt(
    "PROMPT_REASONER", _DEFAULT_REASONER
)
RECOMMENDATION_SYSTEM_PROMPT = _prompt(
    "PROMPT_RECOMMENDATION", _DEFAULT_RECOMMENDATION
)
CONTENT_INTELLIGENCE_SYSTEM_PROMPT = _prompt(
    "PROMPT_CONTENT_INTELLIGENCE", _DEFAULT_CONTENT_INTELLIGENCE
)


if __name__ == "__main__":
    # ponytail: smallest check that fails if env override or fallback breaks
    assert INTENT_EXTRACTION_SYSTEM_PROMPT, "intent prompt empty"
    assert "hook_type" in CONTENT_INTELLIGENCE_SYSTEM_PROMPT, "CI prompt truncated"

    os.environ["PROMPT_REASONER"] = "overridden"
    assert _prompt("PROMPT_REASONER", _DEFAULT_REASONER) == "overridden", "env override failed"

    os.environ["PROMPT_REASONER"] = "   "
    assert _prompt("PROMPT_REASONER", _DEFAULT_REASONER) == _DEFAULT_REASONER, "blank should fall back"

    print("prompts OK — env override and fallback both work")
