from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict):
    session_id: str
    user_query: str
    rewritten_query: str | None
    intent: dict[str, Any] | None
    metadata_filters: dict[str, Any] | None
    retrieval_plan: list[dict[str, Any]] | None
    creator_context: dict[str, Any] | None
    analytics_context: dict[str, Any] | None
    competitor_context: dict[str, Any] | None
    retrieved_documents: list[dict[str, Any]] | None
    ranked_context: dict[str, Any] | None
    confidence_score: float | None
    evidence: dict[str, Any] | None
    response: str | None
    citations: list[dict[str, Any]] | None
    conversation_memory: dict[str, Any] | None
