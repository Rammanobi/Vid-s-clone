from __future__ import annotations

import re
from collections import Counter
from typing import Any


ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "he", "her", "hers", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "me", "my", "myself", "nor", "not", "of", "on", "or", "our", "ours",
    "out", "over", "she", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "then", "there", "these", "they", "this", "those", "to",
    "too", "under", "up", "very", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "you", "your", "yours",
}


def clean_transcript(raw_transcript: str) -> str:
    """Clean transcript: collapse spaces, normalize line breaks, strip punctuation noise."""
    if not raw_transcript:
        return ""

    text = raw_transcript.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n+', '\n', text)

    return text.strip()


def extract_keywords(cleaned_transcript: str, top_n: int = 5) -> list[str]:
    """Extract top N keywords using word frequency, excluding stopwords."""
    if not cleaned_transcript:
        return []

    words = re.findall(r'\b[a-z]+\b', cleaned_transcript.lower())
    filtered = [w for w in words if w not in ENGLISH_STOPWORDS and len(w) > 2]

    if not filtered:
        return []

    counter = Counter(filtered)
    top_keywords = [word for word, _ in counter.most_common(top_n)]

    return top_keywords


def calculate_wpm(word_count: int, duration_sec: float) -> float:
    """Calculate words per minute. Guard against zero duration."""
    if duration_sec <= 0:
        return 0.0
    return round(word_count / (duration_sec / 60), 2)


def clean_and_analyze(
    raw_transcript: str,
    duration_sec: float,
) -> dict[str, Any]:
    """Clean transcript and extract stats."""
    cleaned = clean_transcript(raw_transcript)
    words = cleaned.split()
    word_count = len(words)
    wpm = calculate_wpm(word_count, duration_sec)
    keywords = extract_keywords(cleaned, top_n=5)

    return {
        "clean_transcript": cleaned,
        "word_count": word_count,
        "wpm": wpm,
        "top_keywords": keywords,
    }
