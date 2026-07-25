from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.db import DatabaseClient
from app.graph.registry import registry
from app.graph.state import GraphState
from app.graph.tools import get_conversation_memory
from app.llm import LLMClient
from app.logging_setup import get_logger
from app.reranker import (
    RERANKER_TOP_K,
    compute_retrieval_confidence,
    merge_and_dedup_candidates,
    rerank_candidates,
    select_top_k,
)

logger = get_logger(__name__)

CLARIFYING_THRESHOLD = 0.5
HIGH_CONFIDENCE_THRESHOLD = 0.8

INTENT_EXTRACTION_SYSTEM_PROMPT = (
    "Extract structured intent from a user's query about Instagram Reels content strategy. "
    "Return JSON with keys: intent_type (one of: content_strategy, performance_analysis, "
    "recommendation, trend_discovery, competitor_analysis, general), topic (string or null), "
    "metric (string or null), time_range (string or null), comparison_type (string or null)."
)

QUERY_REWRITE_SYSTEM_PROMPT = (
    "Rewrite the user's query into an optimized search query for finding relevant Instagram "
    "Reels content. Focus on factual, searchable terms. Return JSON with a single key "
    "'rewritten_query' containing the optimized query string."
)

REASONER_SYSTEM_PROMPT = (
    "You are a content strategy analyst for Instagram Reels creators. Based on the evidence "
    "provided, generate a clear, actionable answer. Base your answer strictly on the evidence. "
    "If the evidence is insufficient, acknowledge limitations."
)

RECOMMENDATION_SYSTEM_PROMPT = (
    "Based on the analysis and evidence, generate specific actionable recommendations for "
    "content creation strategy. Return JSON with a single key 'recommendations' containing "
    "an array of recommendation strings."
)


def _config_to_db(config: RunnableConfig) -> DatabaseClient:
    db = config.get("configurable", {}).get("db")
    if db is None:
        raise RuntimeError("Database client not available in graph config")
    return db


def _config_to_llm(config: RunnableConfig) -> LLMClient | None:
    return config.get("configurable", {}).get("llm")


async def conversation_memory_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    db = _config_to_db(config)
    session_id = state.get("session_id", "")
    memory = await get_conversation_memory(db, session_id=session_id)
    logger.debug(
        "conversation_memory_loaded",
        session_id=session_id,
        message_count=memory.get("message_count", 0),
    )
    return {"conversation_memory": memory}


async def query_understanding_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    user_query = state.get("user_query", "")
    llm = _config_to_llm(config)
    intent: dict[str, Any] = {"intent_type": "general", "topic": None}
    metadata_filters: dict[str, Any] = {}

    if llm:
        try:
            result = await llm.extract_structured(
                system_prompt=INTENT_EXTRACTION_SYSTEM_PROMPT,
                user_prompt=f"User query: {user_query}",
                schema={"type": "json_object"},
            )
            if isinstance(result, dict):
                intent_type = result.get("intent_type", "general")
                intent = {
                    "intent_type": intent_type,
                    "topic": result.get("topic"),
                    "metric": result.get("metric"),
                    "time_range": result.get("time_range"),
                    "comparison_type": result.get("comparison_type"),
                }
                if result.get("time_range"):
                    metadata_filters["time_range"] = result["time_range"]
                if result.get("topic"):
                    metadata_filters["topic"] = result["topic"]
        except Exception as exc:
            logger.warning("intent_extraction_failed", error=str(exc))
            intent = {"intent_type": "general", "topic": None}

    if not intent.get("intent_type") or intent["intent_type"] == "general":
        query_lower = user_query.lower()
        if any(w in query_lower for w in ("trend", "trending", "popular")):
            intent["intent_type"] = "trend_discovery"
        elif any(w in query_lower for w in ("competitor", "similar creator", "niche")):
            intent["intent_type"] = "competitor_analysis"
        elif any(w in query_lower for w in ("perform", "analytics", "metric", "engagement", "virality")):
            intent["intent_type"] = "performance_analysis"
        elif any(w in query_lower for w in ("recommend", "suggest", "what should i post", "idea")):
            intent["intent_type"] = "recommendation"
        elif any(w in query_lower for w in ("strategy", "content plan", "what to post")):
            intent["intent_type"] = "content_strategy"

    logger.debug(
        "intent_extracted",
        intent_type=intent.get("intent_type"),
        topic=intent.get("topic"),
    )
    return {"intent": intent, "metadata_filters": metadata_filters}


async def query_transformation_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    user_query = state.get("user_query", "")
    intent = state.get("intent") or {}
    llm = _config_to_llm(config)
    rewritten_query: str | None = None

    if llm:
        try:
            context = f"Intent: {intent.get('intent_type', 'general')}"
            if intent.get("topic"):
                context += f"\nTopic: {intent['topic']}"
            result = await llm.extract_structured(
                system_prompt=QUERY_REWRITE_SYSTEM_PROMPT,
                user_prompt=f"{context}\nOriginal query: {user_query}",
                schema={"type": "json_object"},
            )
            if isinstance(result, dict):
                rewritten_query = result.get("rewritten_query")
        except Exception as exc:
            logger.warning("query_rewrite_failed", error=str(exc))

    if not rewritten_query:
        topic = intent.get("topic")
        if topic:
            rewritten_query = f"{topic} {user_query}"
        else:
            rewritten_query = user_query

    logger.debug("query_rewritten", rewritten_query=rewritten_query)
    return {"rewritten_query": rewritten_query}


async def retrieval_planner_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    intent = state.get("intent") or {}
    intent_type = intent.get("intent_type", "general")
    plan: list[dict[str, Any]] = []

    source_defs = {
        "creator_knowledge": {
            "source": "creator_knowledge",
            "description": "Creator's best topics, hooks, posting patterns",
        },
        "analytics": {
            "source": "analytics",
            "description": "Performance metrics and engagement data",
        },
        "competitor": {
            "source": "competitor",
            "description": "Competitor strategies and benchmarks",
        },
        "trends": {
            "source": "trends",
            "description": "Trending topics and formats",
        },
        "hybrid_search": {
            "source": "hybrid_search",
            "description": "Semantic search across reels and transcripts",
        },
    }

    if intent_type == "content_strategy":
        plan = [
            source_defs["creator_knowledge"],
            source_defs["analytics"],
            source_defs["trends"],
            source_defs["competitor"],
        ]
    elif intent_type == "performance_analysis":
        plan = [
            source_defs["analytics"],
            source_defs["creator_knowledge"],
        ]
    elif intent_type == "recommendation":
        plan = [
            source_defs["creator_knowledge"],
            source_defs["trends"],
            source_defs["competitor"],
            source_defs["hybrid_search"],
        ]
    elif intent_type == "trend_discovery":
        plan = [
            source_defs["trends"],
            source_defs["competitor"],
            source_defs["hybrid_search"],
        ]
    elif intent_type == "competitor_analysis":
        plan = [
            source_defs["competitor"],
            source_defs["trends"],
            source_defs["hybrid_search"],
        ]
    else:
        plan = [
            source_defs["creator_knowledge"],
            source_defs["analytics"],
            source_defs["hybrid_search"],
        ]

    logger.debug(
        "retrieval_planned",
        intent_type=intent_type,
        sources=[p["source"] for p in plan],
    )
    return {"retrieval_plan": plan}


SOURCE_TO_DOC_SOURCES = {
    "creator_knowledge": None,
    "analytics": None,
    "competitor": None,
    "trends": "trends",
    "hybrid_search": "hybrid_search",
}

SOURCE_TO_CONTEXT_KEY = {
    "creator_knowledge": "creator_context",
    "analytics": "analytics_context",
    "competitor": "competitor_context",
}


async def parallel_retrieval_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    db = _config_to_db(config)
    plan = state.get("retrieval_plan") or []
    rewritten_query = state.get("rewritten_query") or state.get("user_query", "")
    intent = state.get("intent") or {}
    topic = intent.get("topic")

    creator_context: dict[str, Any] | None = None
    analytics_context: dict[str, Any] | None = None
    competitor_context: dict[str, Any] | None = None
    retrieved_documents: list[dict[str, Any]] = []

    sources = {p["source"] for p in plan}
    tasks: dict[str, asyncio.Task] = {}

    for source_name in sources:
        tool = registry.get(source_name)
        if tool is None:
            logger.warning("retrieval_source_not_found", source=source_name)
            continue
        if source_name == "creator_knowledge":
            tasks[source_name] = asyncio.create_task(
                registry.execute(source_name, db)
            )
        elif source_name == "analytics":
            tasks[source_name] = asyncio.create_task(
                registry.execute(source_name, db)
            )
        elif source_name == "competitor":
            tasks[source_name] = asyncio.create_task(
                registry.execute(source_name, db, niche=topic or "general")
            )
        elif source_name == "trends":
            tasks[source_name] = asyncio.create_task(
                registry.execute(source_name, db, topic=topic)
            )
        elif source_name == "hybrid_search":
            metadata_filters = state.get("metadata_filters")
            tasks[source_name] = asyncio.create_task(
                registry.execute(
                    source_name, db,
                    query=rewritten_query,
                    metadata_filters=metadata_filters,
                )
            )

    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        task_names = list(tasks.keys())
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.error("retrieval_failed", source=name, error=str(result))
                continue
            doc_source = SOURCE_TO_DOC_SOURCES.get(name)
            if doc_source:
                if isinstance(result, list):
                    retrieved_documents.extend(
                        {"source": doc_source, "data": r} for r in result
                    )
            else:
                ctx_key = SOURCE_TO_CONTEXT_KEY.get(name)
                if ctx_key == "creator_context":
                    creator_context = result
                elif ctx_key == "analytics_context":
                    analytics_context = result
                elif ctx_key == "competitor_context":
                    competitor_context = result

    logger.debug(
        "parallel_retrieval_completed",
        creator=creator_context is not None,
        analytics=analytics_context is not None,
        competitor=competitor_context is not None,
        documents=len(retrieved_documents),
    )
    return {
        "creator_context": creator_context,
        "analytics_context": analytics_context,
        "competitor_context": competitor_context,
        "retrieved_documents": retrieved_documents if retrieved_documents else None,
    }


async def reranker_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    retrieved_documents = state.get("retrieved_documents") or []
    rewritten_query = (state.get("rewritten_query") or "").strip()
    user_query = (state.get("user_query") or "").strip()
    query = rewritten_query or user_query or ""

    if not retrieved_documents:
        return {"ranked_context": state.get("ranked_context") or {}}

    candidates = merge_and_dedup_candidates(retrieved_documents)
    reranked = rerank_candidates(candidates, query)
    top_k = select_top_k(reranked, k=RERANKER_TOP_K)

    ranked_context = state.get("ranked_context") or {}
    ranked_context["reranked_candidates"] = top_k
    ranked_context["reranker_top_k"] = RERANKER_TOP_K

    retrieval_confidence = compute_retrieval_confidence(top_k, query)
    ranked_context["retrieval_confidence"] = retrieval_confidence

    combined = retrieval_confidence.get("combined_score", 0.0)
    current = state.get("confidence_score") or 0.0
    new_confidence = max(combined, current)
    new_confidence = round(min(new_confidence, 1.0), 4)

    return {
        "ranked_context": ranked_context,
        "confidence_score": new_confidence,
    }


async def context_fusion_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    creator_context = state.get("creator_context")
    analytics_context = state.get("analytics_context")
    competitor_context = state.get("competitor_context")
    retrieved_documents = state.get("retrieved_documents") or []
    prev_ranked = state.get("ranked_context") or {}

    ranked_context: dict[str, Any] = {}

    if creator_context:
        ranked_context["creator_profile"] = creator_context

    if analytics_context:
        ranked_context["analytics"] = analytics_context

    if competitor_context:
        ranked_context["competitor_insights"] = competitor_context

    similar_reels = [
        doc["data"]
        for doc in retrieved_documents
        if doc.get("source") in ("hybrid_search", "reranker")
    ]
    if similar_reels:
        ranked_context["similar_reels"] = similar_reels[:5]

    trends = [
        doc["data"]
        for doc in retrieved_documents
        if doc.get("source") == "trends"
    ]
    if trends:
        ranked_context["trend_summary"] = trends[:5]

    retrieval_confidence = prev_ranked.get("retrieval_confidence")
    if retrieval_confidence:
        ranked_context["retrieval_confidence"] = retrieval_confidence

    reranked_candidates = prev_ranked.get("reranked_candidates")
    if reranked_candidates:
        ranked_context["reranked_candidates"] = reranked_candidates
        ranked_context["reranker_top_k"] = prev_ranked.get("reranker_top_k", RERANKER_TOP_K)

    ranked_context["source_count"] = len(ranked_context)
    ranked_context["total_documents"] = len(retrieved_documents)

    logger.debug(
        "context_fused",
        sources=list(ranked_context.keys()),
    )
    return {"ranked_context": ranked_context}


async def confidence_evaluation_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ranked_context = state.get("ranked_context") or {}
    source_count = ranked_context.get("source_count", 0)
    total_documents = ranked_context.get("total_documents", 0)

    retrieval_confidence = ranked_context.get("retrieval_confidence") or {}

    score = 0.0

    retrieval_combined = retrieval_confidence.get("combined_score")
    if retrieval_combined is not None and retrieval_combined > 0:
        score += retrieval_combined * 0.5
    else:
        if source_count >= 3:
            score += 0.4
        elif source_count >= 2:
            score += 0.25
        elif source_count >= 1:
            score += 0.1

        if total_documents >= 10:
            score += 0.3
        elif total_documents >= 5:
            score += 0.2
        elif total_documents >= 1:
            score += 0.1

    if ranked_context.get("analytics"):
        score += 0.15
    if ranked_context.get("creator_profile"):
        score += 0.15

    confidence_score = round(min(score, 1.0), 4)

    logger.debug(
        "confidence_evaluated",
        score=confidence_score,
        source_count=source_count,
        total_documents=total_documents,
        retrieval_confidence=retrieval_combined,
    )
    return {"confidence_score": confidence_score}


async def set_decline_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    response = (
        "I couldn't find sufficient evidence to answer that accurately. "
        "Could you narrow it down to a specific time period or content category?"
    )
    evidence: dict[str, Any] = {"note": "insufficient evidence for confident response", "mode": "decline"}
    logger.debug("response_set", mode="decline", confidence=state.get("confidence_score"))
    return {"response": response, "evidence": evidence}


async def set_clarification_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ranked_context = state.get("ranked_context") or {}
    context_summary = _summarize_context(ranked_context)
    response = (
        f"I found some relevant information, but my confidence is moderate. "
        f"Based on what I found: {context_summary} "
        f"Could you provide more specific details for a more precise answer?"
    )
    evidence: dict[str, Any] = {"note": "partial evidence, clarifying question appended", "mode": "clarify"}
    logger.debug("response_set", mode="clarify", confidence=state.get("confidence_score"))
    return {"response": response, "evidence": evidence}


async def conversational_reasoner_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    # Only reached when confidence_score >= HIGH_CONFIDENCE_THRESHOLD
    user_query = state.get("user_query", "")
    ranked_context = state.get("ranked_context") or {}
    confidence_score = state.get("confidence_score") or 0.0
    llm = _config_to_llm(config)
    response: str | None = None
    evidence: dict[str, Any] = {}

    if llm:
        context_str = _format_context_for_llm(ranked_context)
        try:
            conv_memory = state.get("conversation_memory") or {}
            messages = conv_memory.get("messages", [])
            recent = messages[-6:] if len(messages) > 6 else messages

            llm_messages = [
                {"role": "system", "content": REASONER_SYSTEM_PROMPT},
            ]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                llm_messages.append({"role": role, "content": content})

            llm_messages.append({
                "role": "user",
                "content": (
                    f"User query: {user_query}\n\n"
                    f"Evidence:\n{context_str}\n\n"
                    f"Provide a clear analysis based on the evidence above."
                ),
            })

            data = await llm.chat(llm_messages, temperature=0.3)
            content = data["choices"][0]["message"]["content"]
            response = content
            evidence = {"source": "llm_reasoner", "context_used": list(ranked_context.keys())}
        except Exception as exc:
            logger.warning("reasoner_llm_failed", error=str(exc))
            response = _fallback_reasoning(user_query, ranked_context)
            evidence = {"source": "fallback", "note": str(exc)}
    else:
        response = _fallback_reasoning(user_query, ranked_context)
        evidence = {"source": "fallback", "note": "no llm client available"}

    logger.debug("response_generated", mode="full", confidence=confidence_score)
    return {"response": response, "evidence": evidence}


async def recommendation_generator_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    response = state.get("response")
    ranked_context = state.get("ranked_context") or {}
    confidence = state.get("confidence_score") or 0.0
    llm = _config_to_llm(config)

    if confidence < HIGH_CONFIDENCE_THRESHOLD:
        return {}

    recommendations: list[str] = []

    if llm:
        context_str = _format_context_for_llm(ranked_context)
        try:
            result = await llm.extract_structured(
                system_prompt=RECOMMENDATION_SYSTEM_PROMPT,
                user_prompt=(
                    f"Analysis: {response}\n\nEvidence:\n{context_str}\n\n"
                    f"Generate actionable content strategy recommendations."
                ),
                schema={"type": "json_object"},
            )
            if isinstance(result, dict):
                recs = result.get("recommendations", [])
                if isinstance(recs, list):
                    recommendations = [str(r) for r in recs]
        except Exception as exc:
            logger.warning("recommendation_llm_failed", error=str(exc))

    if not recommendations:
        recommendations = _fallback_recommendations(ranked_context)

    rec_text = "\n\n**Recommendations:**\n" + "\n".join(
        f"- {r}" for r in recommendations
    )
    updated_response = (response or "") + rec_text

    logger.debug(
        "recommendations_generated",
        count=len(recommendations),
    )
    return {"response": updated_response}


async def citation_builder_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    ranked_context = state.get("ranked_context") or {}
    evidence = state.get("evidence") or {}
    citations: list[dict[str, Any]] = []

    creator = ranked_context.get("creator_profile")
    if creator:
        citations.append({
            "source": "creator_profile",
            "type": "creator_knowledge",
            "summary": f"Best topics: {creator.get('best_topics', [])}",
        })

    analytics = ranked_context.get("analytics")
    if analytics:
        citations.append({
            "source": "analytics",
            "type": "performance_data",
            "summary": (
                f"Avg engagement: {analytics.get('avg_engagement_rate')}, "
                f"Reels analyzed: {analytics.get('reel_count')}"
            ),
        })

    competitor = ranked_context.get("competitor_insights")
    if competitor:
        citations.append({
            "source": "competitor_analysis",
            "type": "competitor_intelligence",
            "summary": "Competitor strategies and benchmarks",
        })

    trends = ranked_context.get("trend_summary")
    if trends:
        for t in trends[:3]:
            citations.append({
                "source": "trend_store",
                "type": "trend",
                "summary": t.get("topic", "unknown trend"),
            })

    similar = ranked_context.get("similar_reels")
    if similar:
        for reel in similar[:3]:
            reel_id = reel.get("id") or reel.get("instagramReelId") or "unknown"
            citations.append({
                "source": f"reel:{reel_id}",
                "type": "similar_reel",
                "summary": reel.get("caption", "")[:100],
            })

    citations.append({
        "source": "reasoning",
        "type": "evidence",
        "summary": evidence.get("source", "analysis"),
    })

    logger.debug("citations_built", count=len(citations))
    return {"citations": citations}


PREFERENCE_KEYWORDS: dict[str, str] = {
    "topic": ("topic", "topics", "content about", "niche"),
    "hook_type": ("hook", "hooks", "hook type"),
    "format": ("format", "tutorial", "talking head", "behind the scenes"),
    "posting_day": ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
}

ACCEPT_KEYWORDS = ("yes", "great", "love", "perfect", "thanks", "good idea", "trying", "post")
REJECT_KEYWORDS = ("no", "not", "don't", "bad", "wrong", "dislike", "hate", "different")


def _extract_preferences(query: str) -> dict[str, str]:
    query_lower = query.lower()
    prefs: dict[str, str] = {}
    for key, keywords in PREFERENCE_KEYWORDS.items():
        for kw in keywords:
            if kw in query_lower:
                prefs[key] = kw
                break
    return prefs


def _detect_recommendation_feedback(
    query: str,
    response: str | None,
) -> str | None:
    query_lower = query.lower()
    if has_recommendations := "**Recommendations:**" in (response or ""):
        if any(akw in query_lower for akw in ACCEPT_KEYWORDS):
            return "accepted"
        if any(rkw in query_lower for rkw in REJECT_KEYWORDS):
            return "rejected"
    return None


async def memory_update_node(
    state: GraphState,
    config: RunnableConfig,
) -> dict[str, Any]:
    db = _config_to_db(config)
    session_id = state.get("session_id", "")
    user_query = state.get("user_query", "")
    response = state.get("response")
    citations = state.get("citations")
    conversation_memory = state.get("conversation_memory") or {}

    preferences = _extract_preferences(user_query)
    feedback = _detect_recommendation_feedback(user_query, response)

    stored_preferences = dict(conversation_memory.get("preferences", {}))
    stored_preferences.update(preferences)

    rec_history: list[dict[str, str]] = list(conversation_memory.get("recommendation_history", []))
    if feedback and "**Recommendations:**" in (response or ""):
        rec_history.append({
            "response_snippet": (response or "")[:200],
            "feedback": feedback,
        })

    new_summary = _build_summary(
        conversation_memory.get("summary", ""),
        user_query,
        response or "",
        preferences,
    )

    if session_id:
        try:
            await db.create_chat_message(
                session_id=session_id,
                role="user",
                content=user_query,
            )
            if response:
                await db.create_chat_message(
                    session_id=session_id,
                    role="assistant",
                    content=response,
                    citations=citations,
                )
            if new_summary != conversation_memory.get("summary"):
                await db.update_session_summary(session_id, new_summary)
            logger.debug("memory_updated", session_id=session_id)
        except Exception as exc:
            logger.warning("memory_update_failed", error=str(exc))

    history = conversation_memory.get("messages", [])
    updated_memory: dict[str, Any] = {
        **conversation_memory,
        "message_count": len(history) + 2,
        "preferences": stored_preferences,
        "summary": new_summary,
    }
    if rec_history:
        updated_memory["recommendation_history"] = rec_history

    return {"conversation_memory": updated_memory}


def _build_summary(
    existing_summary: str,
    user_query: str,
    response: str,
    preferences: dict[str, str],
) -> str:
    parts: list[str] = []
    if existing_summary:
        parts.append(existing_summary.rstrip("."))
    topic = preferences.get("topic") or ""
    hook = preferences.get("hook_type") or ""
    if topic or hook:
        prefs = [f"interests: {topic}"] if topic else []
        if hook:
            prefs.append(f"hook: {hook}")
        parts.append(" | ".join(prefs))
    parts.append(f"Q: {user_query[:100]}")
    response_preview = response[:150] if response else ""
    if response_preview:
        parts.append(f"A: {response_preview}")
    combined = "; ".join(parts)
    return combined[:1000]


def _summarize_context(context: dict[str, Any]) -> str:
    parts: list[str] = []
    analytics = context.get("analytics")
    if analytics and analytics.get("reel_count", 0) > 0:
        parts.append(
            f"I see {analytics['reel_count']} reels with "
            f"{analytics.get('avg_engagement_rate', 'N/A')} avg engagement."
        )
    creator = context.get("creator_profile")
    if creator:
        topics = creator.get("best_topics", [])
        if topics:
            parts.append(f"Your best topics include: {', '.join(topics[:3])}.")
    return " ".join(parts) if parts else "Some general information is available."


def _format_context_for_llm(context: dict[str, Any]) -> str:
    lines: list[str] = []
    creator = context.get("creator_profile")
    if creator:
        lines.append("CREATOR PROFILE:")
        lines.append(f"  Best Topics: {creator.get('best_topics', [])}")
        lines.append(f"  Worst Topics: {creator.get('worst_topics', [])}")
        lines.append(f"  Best Hook Types: {creator.get('best_hook_types', [])}")
        lines.append(f"  Best Posting Day: {creator.get('best_posting_day')}")
        lines.append(f"  Best Duration: {creator.get('best_duration_range')}")
        lines.append(f"  Audience Interests: {creator.get('audience_interests', [])}")
        lines.append("")

    analytics = context.get("analytics")
    if analytics:
        lines.append("ANALYTICS:")
        for k, v in analytics.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    competitor = context.get("competitor_insights")
    if competitor:
        lines.append("COMPETITOR INSIGHTS:")
        if isinstance(competitor, dict):
            for k, v in competitor.items():
                lines.append(f"  {k}: {v}")
        lines.append("")

    trends = context.get("trend_summary")
    if trends:
        lines.append("TRENDING:")
        for t in trends:
            lines.append(f"  - {t.get('topic', 'unknown')} (score: {t.get('viralityScore', 'N/A')})")
        lines.append("")

    similar = context.get("similar_reels")
    if similar:
        lines.append("SIMILAR REELS:")
        for reel in similar:
            caption = (reel.get("caption") or "")[:80]
            topic = reel.get("topic") or "unknown"
            lines.append(f"  - [{topic}] {caption}")
        lines.append("")

    return "\n".join(lines)


def _fallback_reasoning(query: str, context: dict[str, Any]) -> str:
    analytics = context.get("analytics")
    creator = context.get("creator_profile")
    parts: list[str] = []

    if analytics and analytics.get("reel_count", 0) > 0:
        parts.append(
            f"Based on analysis of {analytics['reel_count']} reels, "
            f"average engagement rate is {analytics.get('avg_engagement_rate', 'N/A')} "
            f"and average virality score is {analytics.get('avg_virality_score', 'N/A')}."
        )

    if creator:
        topics = creator.get("best_topics", [])
        if topics:
            parts.append(
                f"Your top-performing content topics are: {', '.join(topics[:3])}."
            )
        hooks = creator.get("best_hook_types", [])
        if hooks:
            parts.append(f"Best hook types: {', '.join(hooks[:3])}.")
        posting_day = creator.get("best_posting_day")
        if posting_day:
            parts.append(f"Best posting day: {posting_day}.")

    competitor = context.get("competitor_insights")
    if competitor:
        parts.append("Competitor intelligence is available for benchmarking.")

    trends = context.get("trend_summary")
    if trends:
        trend_names = [t.get("topic", "") for t in trends[:3] if t.get("topic")]
        if trend_names:
            parts.append(f"Current trending topics include: {', '.join(trend_names)}.")

    if not parts:
        return (
            f"Regarding your question about '{query}', I don't have enough "
            f"data to provide a detailed analysis. Try syncing your content data first."
        )

    return " ".join(parts)


def _fallback_recommendations(context: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    creator = context.get("creator_profile")
    if creator:
        topics = creator.get("best_topics", [])
        if topics:
            recs.append(f"Continue creating content about your best topics: {', '.join(topics[:2])}.")
        hooks = creator.get("best_hook_types", [])
        if hooks:
            recs.append(f"Use {hooks[0]} hooks which perform best for your audience.")

    trends = context.get("trend_summary")
    if trends:
        trend_names = [t.get("topic", "") for t in trends[:2] if t.get("topic")]
        if trend_names:
            recs.append(f"Consider creating content about trending topics: {', '.join(trend_names)}.")

    analytics = context.get("analytics")
    if analytics and analytics.get("reel_count", 0) > 0:
        recs.append("Monitor engagement trends regularly to identify emerging patterns.")

    if not recs:
        recs.append("Sync your content data to receive personalized recommendations.")

    return recs
