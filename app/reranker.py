from __future__ import annotations

from typing import Any

from app.logging_setup import get_logger

logger = get_logger(__name__)

RERANKER_TOP_K = 10
HIGH_CONFIDENCE_THRESHOLD = 0.8
CLARIFYING_THRESHOLD = 0.5


def merge_and_dedup_candidates(
    retrieved_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    for doc_wrapper in retrieved_documents:
        data = doc_wrapper.get("data") or {}
        reel_id = data.get("reel_id") or data.get("id") or ""
        if not reel_id or reel_id in seen:
            continue
        seen.add(reel_id)

        retrieval_score = data.get("retrieval_score")
        bm25_score = data.get("bm25_score")
        contexts = data.get("contexts") or []

        fused_score = _fuse_scores(retrieval_score, bm25_score)

        merged.append({
            "reel_id": reel_id,
            "fused_score": fused_score,
            "retrieval_score": retrieval_score,
            "bm25_score": bm25_score,
            "contexts": contexts,
            "topic": data.get("topic", ""),
            "hook_text": data.get("hook_text", ""),
            "content_format": data.get("content_format", ""),
            "hook_type": data.get("hook_type", ""),
            "caption": data.get("caption", ""),
            "duration_sec": data.get("duration_sec", 0.0),
        })

    merged.sort(key=lambda x: x["fused_score"], reverse=True)
    return merged


def _fuse_scores(
    retrieval_score: float | None,
    bm25_score: float | None,
) -> float:
    scores: list[float] = []
    if retrieval_score is not None and retrieval_score > 0:
        scores.append(retrieval_score)
    if bm25_score is not None and bm25_score > 0:
        scores.append(bm25_score)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def rerank_candidates(
    candidates: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    if not query or not candidates:
        return candidates

    query_lower = query.lower()
    query_terms = [w for w in query_lower.split() if len(w) > 1]

    for cand in candidates:
        reranker_score = _compute_reranker_score(cand, query_terms, query_lower)
        cand["reranker_score"] = reranker_score

    candidates.sort(key=lambda x: x.get("reranker_score", 0.0), reverse=True)
    return candidates


def _compute_reranker_score(
    candidate: dict[str, Any],
    query_terms: list[str],
    query_lower: str,
) -> float:
    score = 0.0
    text_sources: list[str] = []

    caption = candidate.get("caption", "")
    if caption:
        text_sources.append(str(caption).lower())

    topic = candidate.get("topic", "")
    if topic:
        text_sources.append(str(topic).lower())

    hook_text = candidate.get("hook_text", "")
    if hook_text:
        text_sources.append(str(hook_text).lower())

    contexts = candidate.get("contexts") or []
    for ctx in contexts:
        if ctx and str(ctx).strip():
            text_sources.append(str(ctx).lower())

    combined_text = " ".join(text_sources)

    if not combined_text:
        return 0.0

    exact_match_count = 0
    term_match_count = 0
    for term in query_terms:
        if term in combined_text:
            term_match_count += 1
            if term in query_lower and term in combined_text:
                exact_match_count += 1

    if query_terms:
        term_coverage = term_match_count / len(query_terms)
        score += term_coverage * 0.4

    fused = candidate.get("fused_score") or 0.0
    score += fused * 0.3

    retrieval = candidate.get("retrieval_score")
    if retrieval is not None and retrieval > 0:
        score += retrieval * 0.2

    bm25 = candidate.get("bm25_score")
    if bm25 is not None and bm25 > 0:
        score += bm25 * 0.1

    return round(min(score, 1.0), 4)


def select_top_k(
    candidates: list[dict[str, Any]],
    k: int = RERANKER_TOP_K,
) -> list[dict[str, Any]]:
    return candidates[:k]


def compute_retrieval_confidence(
    candidates: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    if not candidates or not query:
        return {
            "retrieval_score": 0.0,
            "reranker_score": 0.0,
            "coverage_score": 0.0,
            "combined_score": 0.0,
        }

    retrieval_scores = [
        c.get("retrieval_score") for c in candidates
        if c.get("retrieval_score") is not None
    ]
    reranker_scores = [
        c.get("reranker_score") for c in candidates
        if c.get("reranker_score") is not None
    ]
    bm25_scores = [
        c.get("bm25_score") for c in candidates
        if c.get("bm25_score") is not None
    ]

    retrieval_score = max(retrieval_scores) if retrieval_scores else 0.0
    reranker_score = max(reranker_scores) if reranker_scores else 0.0

    query_lower = query.lower()
    query_terms = [w for w in query_lower.split() if len(w) > 1]
    if query_terms:
        covered_terms: set[str] = set()
        for cand in candidates:
            cand_text = _get_candidate_text(cand)
            for term in query_terms:
                if term in cand_text:
                    covered_terms.add(term)
        coverage_score = len(covered_terms) / len(query_terms)
    else:
        coverage_score = 0.0

    combined_score = (
        retrieval_score * 0.35 +
        reranker_score * 0.40 +
        coverage_score * 0.25
    )

    return {
        "retrieval_score": round(retrieval_score, 4),
        "reranker_score": round(reranker_score, 4),
        "coverage_score": round(coverage_score, 4),
        "combined_score": round(min(combined_score, 1.0), 4),
    }


def _get_candidate_text(candidate: dict[str, Any]) -> str:
    parts: list[str] = []
    caption = candidate.get("caption", "")
    if caption:
        parts.append(str(caption).lower())
    topic = candidate.get("topic", "")
    if topic:
        parts.append(str(topic).lower())
    hook_text = candidate.get("hook_text", "")
    if hook_text:
        parts.append(str(hook_text).lower())
    contexts = candidate.get("contexts") or []
    for ctx in contexts:
        if ctx and str(ctx).strip():
            parts.append(str(ctx).lower())
    return " ".join(parts)
