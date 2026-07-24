from __future__ import annotations

import re
from typing import Any

from app.logging_setup import get_logger
from app.schema_validator import (
    ContentFormat,
    ContentIntelligenceSchema,
    HookType,
)

logger = get_logger(__name__)

_HOOK_PATTERNS: list[tuple[re.Pattern[str], HookType]] = [
    (re.compile(r"you won't believe|wait till you|mind blown|shocked", re.I), HookType.CURIOSITY),
    (re.compile(r"hot take|unpopular opinion|controversial|change my mind", re.I), HookType.CONTRARIAN),
    (re.compile(r"let me tell you a story|when I was|back in the day", re.I), HookType.STORY),
    (re.compile(r"how to|step by step|the secret to|here's how|tip for|trick for", re.I), HookType.PROBLEM_SOLUTION),
    (re.compile(r"^why|^what|^how|^when|^where|^do you|^have you|^can you|question of the day", re.I), HookType.QUESTION),
]

_CTA_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"follow|subscribe|like|comment|share|save this|tag a|link in bio", re.I),
    re.compile(r"check out|click the|swipe up|drop a comment|let me know", re.I),
    re.compile(r"don't forget to|make sure to|go follow|turn on notifications", re.I),
]

_CONTENT_FORMAT_KEYWORDS: list[tuple[list[str], ContentFormat]] = [
    (["tutorial", "how to", "step", "guide", "learn", "lesson"], ContentFormat.TUTORIAL),
    (["behind the scenes", "bts", "sneak peek", "exclusive look"], ContentFormat.BEHIND_THE_SCENES),
    (["talking head", "speaking", "monologue", "explain", "tell you"], ContentFormat.TALKING_HEAD),
    (["screen recording", "screen capture", "screen share", "desktop"], ContentFormat.SCREEN_RECORDING),
    (["skit", "comedy", "funny", "humor", "parody", "impression"], ContentFormat.SKIT),
]

_SENTIMENT_POSITIVE = re.compile(
    r"amazing|incredible|love|great|best|perfect|beautiful|awesome|fantastic|wonderful|excellent", re.I
)
_SENTIMENT_NEGATIVE = re.compile(
    r"terrible|awful|hate|worst|horrible|disgusting|ugly|stupid|boring|waste", re.I
)
_SENTIMENT_NEUTRAL = re.compile(
    r"learn|how to|tutorial|step|guide|explain|information|overview", re.I
)


def extract_intelligence(
    reel_db_id: str,
    transcript: str | None = None,
    caption: str | None = None,
    text_overlays: list[str] | None = None,
    visual_topics: list[str] | None = None,
    visual_summary: str | None = None,
) -> ContentIntelligenceSchema:
    combined_text = " ".join(
        filter(None, [transcript, caption, *(text_overlays or [])])
    ).strip()

    topic = _extract_topic(visual_topics, combined_text, visual_summary)
    hook_type, hook_text = _extract_hook(combined_text)
    cta = _extract_cta(combined_text)
    content_format = _extract_content_format(visual_topics, combined_text, visual_summary)
    teaching_style = _extract_teaching_style(combined_text, content_format)
    narrative_style = _extract_narrative_style(combined_text, content_format)
    audience_intent = _extract_audience_intent(combined_text, visual_topics)
    sentiment = _extract_sentiment(combined_text)
    visual_style = _extract_visual_style(visual_topics, visual_summary)

    return ContentIntelligenceSchema(
        reel_id=reel_db_id,
        topic=topic,
        hook_type=hook_type,
        hook_text=hook_text,
        cta=cta,
        content_format=content_format,
        teaching_style=teaching_style,
        narrative_style=narrative_style,
        audience_intent=audience_intent,
        sentiment=sentiment,
        visual_style=visual_style,
    )


def _extract_topic(
    visual_topics: list[str] | None,
    combined_text: str,
    visual_summary: str | None,
) -> str | None:
    topics: list[str] = []

    if visual_topics:
        topics.extend(visual_topics[:3])

    if visual_summary:
        topics.append(visual_summary[:200])

    if combined_text:
        words = [w for w in combined_text.split() if len(w) > 3]
        freq: dict[str, int] = {}
        for w in words:
            freq[w.lower()] = freq.get(w.lower(), 0) + 1
        if freq:
            top_word = max(freq, key=freq.get)
            if top_word not in [t.lower().replace(" ", "_") for t in topics]:
                topics.append(top_word)

    return "; ".join(topics[:5]) if topics else None


def _extract_hook(text: str) -> tuple[HookType | None, str | None]:
    for pattern, hook_type in _HOOK_PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            return hook_type, context
    return None, None


def _extract_cta(text: str) -> str | None:
    for pattern in _CTA_PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            return text[start:end].strip()
    return None


def _extract_content_format(
    visual_topics: list[str] | None,
    combined_text: str,
    visual_summary: str | None,
) -> ContentFormat | None:
    sources = [
        t for t in (visual_topics or [])
    ] + [
        visual_summary or ""
    ]

    for keywords, fmt in _CONTENT_FORMAT_KEYWORDS:
        for kw in keywords:
            if kw in combined_text.lower():
                return fmt
            for src in sources:
                if kw in src.lower():
                    return fmt

    if visual_topics:
        if "person talking" in visual_topics or "close up face" in visual_topics:
            return ContentFormat.TALKING_HEAD
        if "text on screen" in visual_topics:
            return ContentFormat.TUTORIAL

    return None


def _extract_teaching_style(
    combined_text: str,
    content_format: ContentFormat | None,
) -> str | None:
    if content_format == ContentFormat.TUTORIAL:
        return "Step-by-step"
    if re.search(r"first|next|then|finally|step \d", combined_text, re.I):
        return "Step-by-step"
    if re.search(r"because|reason|explain|how it works", combined_text, re.I):
        return "Explanatory"
    if re.search(r"tip|trick|hack|secret|pro tip", combined_text, re.I):
        return "Tip-based"
    return None


def _extract_narrative_style(
    combined_text: str,
    content_format: ContentFormat | None,
) -> str | None:
    if re.search(
        r"let me tell you|when I|my story|happened to me", combined_text, re.I
    ):
        return "Storytelling"
    if re.search(r"you should|you need to|you must|do this", combined_text, re.I):
        return "Direct advice"
    if re.search(r"question|what do you think|would you", combined_text, re.I):
        return "Conversational"
    return None


def _extract_audience_intent(
    combined_text: str,
    visual_topics: list[str] | None,
) -> str | None:
    if re.search(r"learn|understand|know how|comprehend", combined_text, re.I):
        return "Educational"
    if re.search(r"buy|shop|product|deal|discount|price", combined_text, re.I):
        return "Promotional"
    if re.search(r"funny|laugh|hilarious|entertain", combined_text, re.I):
        return "Entertainment"
    if re.search(r"inspire|motivate|keep going|never give up", combined_text, re.I):
        return "Inspirational"
    if visual_topics and "technology and gadgets" in visual_topics:
        return "Educational"
    if visual_topics and "food and cooking" in visual_topics:
        return "Educational"
    return None


def _extract_sentiment(text: str) -> str | None:
    if not text:
        return None

    pos = len(_SENTIMENT_POSITIVE.findall(text))
    neg = len(_SENTIMENT_NEGATIVE.findall(text))
    neut = len(_SENTIMENT_NEUTRAL.findall(text))

    if pos > neg and pos > neut:
        return "positive"
    if neg > pos and neg > neut:
        return "negative"
    if neut > 0:
        return "neutral"
    return "neutral"


def _extract_visual_style(
    visual_topics: list[str] | None,
    visual_summary: str | None,
) -> str | None:
    if not visual_topics:
        return None

    styles: list[str] = []
    if "outdoor setting" in visual_topics or "nature landscape" in visual_topics:
        styles.append("Outdoor")
    if "indoor setting" in visual_topics:
        styles.append("Indoor")
    if "close up face" in visual_topics:
        styles.append("Close-up")
    if "text on screen" in visual_topics:
        styles.append("Text-heavy")
    if "animation" in visual_topics:
        styles.append("Animated")
    if "night scene" in visual_topics:
        styles.append("Night")
    if "underwater" in visual_topics:
        styles.append("Underwater")

    return "; ".join(styles) if styles else None