from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.graph.graph import (
    CLARIFYING_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    _route_after_confidence,
    _route_after_reasoner,
    build_conversation_graph,
    compiled_graph,
)
from app.graph.nodes import (
    citation_builder_node,
    confidence_evaluation_node,
    context_fusion_node,
    conversational_reasoner_node,
    conversation_memory_node,
    memory_update_node,
    parallel_retrieval_node,
    query_transformation_node,
    query_understanding_node,
    recommendation_generator_node,
    retrieval_planner_node,
    set_clarification_node,
    set_decline_node,
)
from app.graph.registry import ToolInfo, ToolRegistry, registry
from app.graph.state import GraphState
from app.graph.tools import (
    get_analytics,
    get_competitor_insights,
    get_conversation_memory,
    get_creator_knowledge,
    get_trending_data,
    hybrid_search,
)

pytestmark = pytest.mark.asyncio

STATE: GraphState = {
    "session_id": "test-session",
    "user_query": "what should I post next",
    "rewritten_query": None,
    "intent": None,
    "metadata_filters": None,
    "retrieval_plan": None,
    "creator_context": None,
    "analytics_context": None,
    "competitor_context": None,
    "retrieved_documents": None,
    "ranked_context": None,
    "confidence_score": None,
    "evidence": None,
    "response": None,
    "citations": None,
    "conversation_memory": None,
}


def _make_config(db: Any | None = None, llm: Any | None = None) -> dict:
    return {"configurable": {"db": db, "llm": llm}}


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = ToolInfo(name="test_tool", description="test", func=lambda db: {})
        reg.register(tool)
        assert reg.get("test_tool") is tool

    def test_get_missing(self) -> None:
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_has_tool(self) -> None:
        reg = ToolRegistry()
        reg.register(ToolInfo(name="a", description="d", func=lambda db: {}))
        assert reg.has_tool("a") is True
        assert reg.has_tool("b") is False

    def test_list_tools(self) -> None:
        reg = ToolRegistry()
        reg.register(ToolInfo(name="a", description="d1", func=lambda db: {}))
        reg.register(ToolInfo(name="b", description="d2", func=lambda db: {}))
        names = [t.name for t in reg.list_tools()]
        assert "a" in names
        assert "b" in names

    def test_tool_names(self) -> None:
        reg = ToolRegistry()
        reg.register(ToolInfo(name="a", description="d1", func=lambda db: {}))
        assert reg.tool_names() == ["a"]

    async def test_execute(self) -> None:
        reg = ToolRegistry()
        async def my_tool(db: Any) -> dict:
            return {"result": "ok"}
        reg.register(ToolInfo(name="t", description="d", func=my_tool))
        result = await reg.execute("t", AsyncMock())
        assert result == {"result": "ok"}

    async def test_execute_missing_raises(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
            await reg.execute("nonexistent", AsyncMock())

    async def test_read_only_enforced(self) -> None:
        reg = ToolRegistry()
        async def write_tool(db: Any) -> dict:
            return {"write": True}
        reg.register(ToolInfo(name="w", description="d", func=write_tool, read_only=False))
        result = await reg.execute("w", AsyncMock())
        assert result["write"] is True

    def test_global_registry_has_tools(self) -> None:
        names = registry.tool_names()
        assert "creator_knowledge" in names
        assert "analytics" in names
        assert "hybrid_search" in names
        assert "competitor" in names
        assert "trends" in names
        assert "conversation_memory" in names

    def test_global_registry_all_read_only(self) -> None:
        for tool in registry.list_tools():
            assert tool.read_only is True


class TestConversationMemoryNode:
    async def test_loads_memory(self) -> None:
        db = AsyncMock()
        db.get_chat_messages = AsyncMock(return_value=[{"role": "user", "content": "hi"}])
        db.get_session = AsyncMock(return_value={"id": "s1", "summary": "test"})
        result = await conversation_memory_node(STATE, _make_config(db=db))
        assert result["conversation_memory"]["message_count"] == 1
        assert result["conversation_memory"]["session"]["summary"] == "test"

    async def test_empty_session(self) -> None:
        db = AsyncMock()
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_session = AsyncMock(return_value=None)
        result = await conversation_memory_node(STATE, _make_config(db=db))
        assert result["conversation_memory"]["message_count"] == 0
        assert result["conversation_memory"]["session"] is None

    async def test_missing_db_raises(self) -> None:
        with pytest.raises(RuntimeError, match="Database client not available"):
            await conversation_memory_node(STATE, _make_config(db=None))


class TestQueryUnderstandingNode:
    async def test_with_llm(self) -> None:
        llm = AsyncMock()
        llm.extract_structured = AsyncMock(
            return_value={
                "intent_type": "content_strategy",
                "topic": "AI Tutorials",
                "metric": "engagement",
                "time_range": "30_days",
            }
        )
        result = await query_understanding_node(STATE, _make_config(llm=llm))
        assert result["intent"]["intent_type"] == "content_strategy"
        assert result["intent"]["topic"] == "AI Tutorials"
        assert result["metadata_filters"]["time_range"] == "30_days"

    async def test_without_llm_fallback(self) -> None:
        result = await query_understanding_node(STATE, _make_config())
        assert result["intent"]["intent_type"] == "recommendation"
        assert result["intent"]["topic"] is None

    async def test_trend_discovery_detection(self) -> None:
        state = {**STATE, "user_query": "what are the trending topics"}
        result = await query_understanding_node(state, _make_config())
        assert result["intent"]["intent_type"] == "trend_discovery"

    async def test_performance_analysis_detection(self) -> None:
        state = {**STATE, "user_query": "how did my reels perform"}
        result = await query_understanding_node(state, _make_config())
        assert result["intent"]["intent_type"] == "performance_analysis"

    async def test_competitor_detection(self) -> None:
        state = {**STATE, "user_query": "analyze my competitors"}
        result = await query_understanding_node(state, _make_config())
        assert result["intent"]["intent_type"] == "competitor_analysis"

    async def test_llm_failure_falls_back(self) -> None:
        llm = AsyncMock()
        llm.extract_structured = AsyncMock(side_effect=RuntimeError("API down"))
        state = {**STATE, "user_query": "trending now"}
        result = await query_understanding_node(state, _make_config(llm=llm))
        assert result["intent"]["intent_type"] == "trend_discovery"

    async def test_general_intent_no_keywords(self) -> None:
        state = {**STATE, "user_query": "hello"}
        result = await query_understanding_node(state, _make_config())
        assert result["intent"]["intent_type"] == "general"


class TestQueryTransformationNode:
    async def test_with_llm(self) -> None:
        llm = AsyncMock()
        llm.extract_structured = AsyncMock(
            return_value={"rewritten_query": "AI tutorials best engagement hooks"}
        )
        state = {**STATE, "user_query": "what works for AI tutorials"}
        result = await query_transformation_node(state, _make_config(llm=llm))
        assert result["rewritten_query"] == "AI tutorials best engagement hooks"

    async def test_without_llm(self) -> None:
        result = await query_transformation_node(STATE, _make_config())
        assert result["rewritten_query"] == STATE["user_query"]

    async def test_with_topic(self) -> None:
        state = {
            **STATE,
            "user_query": "best hooks",
            "intent": {"intent_type": "content_strategy", "topic": "AI"},
        }
        result = await query_transformation_node(state, _make_config())
        assert "AI" in result["rewritten_query"]

    async def test_llm_failure(self) -> None:
        llm = AsyncMock()
        llm.extract_structured = AsyncMock(side_effect=RuntimeError("fail"))
        result = await query_transformation_node(STATE, _make_config(llm=llm))
        assert result["rewritten_query"] == STATE["user_query"]


class TestRetrievalPlannerNode:
    def _make(self, intent_type: str) -> GraphState:
        return {**STATE, "intent": {"intent_type": intent_type, "topic": None}}

    async def test_content_strategy(self) -> None:
        result = await retrieval_planner_node(self._make("content_strategy"), _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert "creator_knowledge" in sources
        assert "analytics" in sources
        assert "trends" in sources
        assert "competitor" in sources

    async def test_performance_analysis(self) -> None:
        result = await retrieval_planner_node(self._make("performance_analysis"), _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert "analytics" in sources
        assert "creator_knowledge" in sources

    async def test_recommendation(self) -> None:
        result = await retrieval_planner_node(self._make("recommendation"), _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert "creator_knowledge" in sources
        assert "trends" in sources

    async def test_trend_discovery(self) -> None:
        result = await retrieval_planner_node(self._make("trend_discovery"), _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert "trends" in sources
        assert "competitor" in sources

    async def test_competitor_analysis(self) -> None:
        result = await retrieval_planner_node(self._make("competitor_analysis"), _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert "competitor" in sources
        assert "hybrid_search" in sources

    async def test_general(self) -> None:
        result = await retrieval_planner_node(self._make("general"), _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert len(sources) >= 2
        assert "creator_knowledge" in sources
        assert "analytics" in sources

    async def test_none_intent(self) -> None:
        result = await retrieval_planner_node({**STATE, "intent": None}, _make_config())
        sources = [p["source"] for p in result["retrieval_plan"]]
        assert "creator_knowledge" in sources
        assert "analytics" in sources


class TestParallelRetrievalNode:
    async def test_all_sources_via_registry(self) -> None:
        db = AsyncMock()
        db.get_creator_profile = AsyncMock(
            return_value={"bestTopics": ["AI"], "bestHookTypes": ["CURIOSITY"]}
        )
        db.get_reels_with_metrics = AsyncMock(
            return_value=[{"engagementRate": 0.05, "views": 100, "likes": 10}]
        )
        db.get_competitor_insights_by_niche = AsyncMock(
            return_value=[{"competitorId": "c1", "avgVirality": 2.0}]
        )
        db.get_trends_by_topic = AsyncMock(
            return_value=[{"topic": "AI trends", "viralityScore": 3.0}]
        )
        db.search_reels_hybrid = AsyncMock(
            return_value=[{"reel_id": "r1", "retrieval_score": 0.92, "contexts": ["test reel"]}]
        )
        db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[{"id": "r1", "caption": "test reel", "topic": "AI"}]
        )

        state: GraphState = {
            **STATE,
            "retrieval_plan": [
                {"source": "creator_knowledge"},
                {"source": "analytics"},
                {"source": "competitor"},
                {"source": "trends"},
                {"source": "hybrid_search"},
            ],
            "rewritten_query": "AI content",
        }
        result = await parallel_retrieval_node(state, _make_config(db=db))
        assert result["creator_context"] is not None
        assert result["analytics_context"] is not None
        assert result["competitor_context"] is not None
        assert len(result["retrieved_documents"]) >= 2

    async def test_no_plan(self) -> None:
        result = await parallel_retrieval_node(STATE, _make_config(db=AsyncMock()))
        assert result["creator_context"] is None
        assert result["analytics_context"] is None

    async def test_partial_failure(self) -> None:
        db = AsyncMock()
        db.get_creator_profile = AsyncMock(side_effect=RuntimeError("db fail"))
        db.get_reels_with_metrics = AsyncMock(
            return_value=[{"engagementRate": 0.05, "views": 100, "likes": 10}]
        )
        db.get_trends_by_topic = AsyncMock(
            return_value=[{"topic": "trend", "viralityScore": 1.0}]
        )
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])
        state: GraphState = {
            **STATE,
            "retrieval_plan": [
                {"source": "creator_knowledge"},
                {"source": "analytics"},
                {"source": "trends"},
            ],
        }

        with patch("app.graph.nodes.logger") as mock_log:
            result = await parallel_retrieval_node(state, _make_config(db=db))

        assert result["creator_context"] is None
        assert result["analytics_context"] is not None
        assert mock_log.error.called

    async def test_unknown_source_logs_warning(self) -> None:
        db = AsyncMock()
        state: GraphState = {
            **STATE,
            "retrieval_plan": [{"source": "nonexistent_tool"}],
        }
        with patch("app.graph.nodes.logger") as mock_log:
            result = await parallel_retrieval_node(state, _make_config(db=db))
        assert result["creator_context"] is None
        assert result["analytics_context"] is None


class TestContextFusionNode:
    async def test_merges_all_sources(self) -> None:
        state: GraphState = {
            **STATE,
            "creator_context": {"best_topics": ["AI"]},
            "analytics_context": {"reel_count": 10},
            "competitor_context": {"avg_virality": 2.0},
            "retrieved_documents": [
                {"source": "hybrid_search", "data": {"id": "r1"}},
                {"source": "hybrid_search", "data": {"id": "r2"}},
                {"source": "trends", "data": {"topic": "trend1"}},
            ],
        }
        result = await context_fusion_node(state, _make_config())
        rc = result["ranked_context"]
        assert "creator_profile" in rc
        assert "analytics" in rc
        assert "competitor_insights" in rc
        assert "similar_reels" in rc
        assert "trend_summary" in rc
        assert rc["source_count"] == 5

    async def test_empty_context(self) -> None:
        result = await context_fusion_node(STATE, _make_config())
        assert result["ranked_context"]["source_count"] == 0

    async def test_only_creator(self) -> None:
        state: GraphState = {
            **STATE,
            "creator_context": {"best_topics": ["AI"]},
        }
        result = await context_fusion_node(state, _make_config())
        assert result["ranked_context"]["source_count"] == 1
        assert "creator_profile" in result["ranked_context"]


class TestConfidenceEvaluationNode:
    async def test_high_confidence(self) -> None:
        state: GraphState = {
            **STATE,
            "ranked_context": {
                "source_count": 3,
                "total_documents": 15,
                "analytics": {"reel_count": 10},
                "creator_profile": {"best_topics": ["AI"]},
            },
        }
        result = await confidence_evaluation_node(state, _make_config())
        assert result["confidence_score"] >= HIGH_CONFIDENCE_THRESHOLD

    async def test_low_confidence(self) -> None:
        state: GraphState = {
            **STATE,
            "ranked_context": {"source_count": 0, "total_documents": 0},
        }
        result = await confidence_evaluation_node(state, _make_config())
        assert result["confidence_score"] < CLARIFYING_THRESHOLD

    async def test_medium_confidence(self) -> None:
        state: GraphState = {
            **STATE,
            "ranked_context": {
                "source_count": 2,
                "total_documents": 3,
                "analytics": {"reel_count": 5},
            },
        }
        result = await confidence_evaluation_node(state, _make_config())
        assert CLARIFYING_THRESHOLD <= result["confidence_score"] < HIGH_CONFIDENCE_THRESHOLD

    async def test_empty_ranked_context(self) -> None:
        state: GraphState = {**STATE, "ranked_context": {}}
        result = await confidence_evaluation_node(state, _make_config())
        assert result["confidence_score"] == 0.0


class TestSetDeclineNode:
    async def test_decline_message(self) -> None:
        state: GraphState = {**STATE, "confidence_score": 0.3}
        result = await set_decline_node(state, _make_config())
        assert "couldn't find sufficient evidence" in (result["response"] or "").lower()
        assert result["evidence"]["mode"] == "decline"

    async def test_decline_evidence_note(self) -> None:
        result = await set_decline_node(STATE, _make_config())
        assert "insufficient evidence" in result["evidence"]["note"]


class TestSetClarificationNode:
    async def test_clarify_message_with_context(self) -> None:
        state: GraphState = {
            **STATE,
            "confidence_score": 0.6,
            "ranked_context": {
                "analytics": {"reel_count": 5, "avg_engagement_rate": 0.03},
                "creator_profile": {"best_topics": ["AI"]},
            },
        }
        result = await set_clarification_node(state, _make_config())
        assert "moderate" in (result["response"] or "").lower()
        assert result["evidence"]["mode"] == "clarify"
        assert "reels" in (result["response"] or "")

    async def test_clarify_without_context(self) -> None:
        result = await set_clarification_node(STATE, _make_config())
        assert result["response"] is not None


class TestConversationalReasonerNode:
    async def test_high_confidence_fallback(self) -> None:
        state: GraphState = {
            **STATE,
            "confidence_score": 0.9,
            "ranked_context": {
                "analytics": {"reel_count": 10, "avg_engagement_rate": 0.05, "avg_virality_score": 2.0},
                "creator_profile": {
                    "best_topics": ["AI Tutorials"],
                    "best_hook_types": ["CURIOSITY"],
                    "best_posting_day": "Wednesday",
                },
            },
        }
        result = await conversational_reasoner_node(state, _make_config())
        assert result["response"] is not None
        assert result["evidence"]["source"] == "fallback"

    async def test_high_confidence_with_llm(self) -> None:
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Your best content topic is AI tutorials."}}]
            }
        )
        state: GraphState = {
            **STATE,
            "confidence_score": 0.9,
            "ranked_context": {
                "analytics": {"reel_count": 10},
                "creator_profile": {"best_topics": ["AI Tutorials"]},
            },
        }
        result = await conversational_reasoner_node(state, _make_config(llm=llm))
        assert "AI tutorials" in (result["response"] or "")
        assert result["evidence"]["source"] == "llm_reasoner"

    async def test_uses_conversation_history(self) -> None:
        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value={"choices": [{"message": {"content": "Based on history..."}}]}
        )
        state: GraphState = {
            **STATE,
            "confidence_score": 0.9,
            "ranked_context": {"analytics": {"reel_count": 5}},
            "conversation_memory": {
                "messages": [
                    {"role": "user", "content": "previous question"},
                    {"role": "assistant", "content": "previous answer"},
                ]
            },
        }
        result = await conversational_reasoner_node(state, _make_config(llm=llm))
        assert result["response"] is not None


class TestRecommendationGeneratorNode:
    async def test_high_confidence_fallback(self) -> None:
        state: GraphState = {
            **STATE,
            "confidence_score": 0.9,
            "response": "analysis result",
            "ranked_context": {
                "creator_profile": {
                    "best_topics": ["AI", "tutorials"],
                    "best_hook_types": ["CURIOSITY"],
                },
                "trend_summary": [{"topic": "AI trends"}],
                "analytics": {"reel_count": 10},
            },
        }
        result = await recommendation_generator_node(state, _make_config())
        assert result["response"] is not None
        assert "**Recommendations:**" in result["response"]

    async def test_high_confidence_with_llm(self) -> None:
        llm = AsyncMock()
        llm.extract_structured = AsyncMock(
            return_value={"recommendations": ["Create more AI tutorials", "Use curiosity hooks"]}
        )
        state: GraphState = {
            **STATE,
            "confidence_score": 0.9,
            "response": "base analysis",
            "ranked_context": {},
        }
        result = await recommendation_generator_node(state, _make_config(llm=llm))
        assert "Create more AI tutorials" in result["response"]

    async def test_llm_failure_falls_back(self) -> None:
        llm = AsyncMock()
        llm.extract_structured = AsyncMock(side_effect=RuntimeError("fail"))
        state: GraphState = {
            **STATE,
            "confidence_score": 0.9,
            "response": "base analysis",
            "ranked_context": {},
        }
        result = await recommendation_generator_node(state, _make_config(llm=llm))
        assert "**Recommendations:**" in result["response"]


class TestCitationBuilderNode:
    async def test_builds_citations(self) -> None:
        state: GraphState = {
            **STATE,
            "ranked_context": {
                "creator_profile": {"best_topics": ["AI"]},
                "analytics": {"reel_count": 10, "avg_engagement_rate": 0.05},
                "competitor_insights": {"data": "yes"},
                "trend_summary": [{"topic": "trend1"}, {"topic": "trend2"}],
                "similar_reels": [
                    {"id": "r1", "caption": "caption1"},
                    {"id": "r2", "caption": "caption2"},
                ],
            },
            "evidence": {"source": "llm_reasoner"},
        }
        result = await citation_builder_node(state, _make_config())
        assert len(result["citations"]) >= 6

    async def test_empty_context(self) -> None:
        state: GraphState = {
            **STATE,
            "ranked_context": {},
            "evidence": {},
        }
        result = await citation_builder_node(state, _make_config())
        assert len(result["citations"]) == 1
        assert result["citations"][0]["source"] == "reasoning"

    async def test_includes_reasoning_source(self) -> None:
        state: GraphState = {
            **STATE,
            "ranked_context": {},
            "evidence": {"source": "fallback"},
        }
        result = await citation_builder_node(state, _make_config())
        assert any(c["source"] == "reasoning" for c in result["citations"])


class TestMemoryUpdateNode:
    async def test_saves_messages(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(
            side_effect=[
                {"id": "msg1"},
                {"id": "msg2"},
            ]
        )
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "response": "test response",
            "citations": [{"source": "test"}],
            "conversation_memory": {"messages": [{"role": "user", "content": "prev"}]},
        }
        result = await memory_update_node(state, _make_config(db=db))
        assert db.create_chat_message.call_count == 2
        assert result["conversation_memory"]["message_count"] == 3

    async def test_no_session_skips(self) -> None:
        state: GraphState = {
            **STATE,
            "session_id": "",
            "response": "test",
            "conversation_memory": {"messages": []},
        }
        result = await memory_update_node(state, _make_config(db=AsyncMock()))
        assert result["conversation_memory"]["message_count"] == 2

    async def test_db_failure_logged(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(side_effect=RuntimeError("db fail"))
        state: GraphState = {
            **STATE,
            "response": "test",
            "conversation_memory": {"messages": []},
        }
        result = await memory_update_node(state, _make_config(db=db))
        assert result["conversation_memory"]["message_count"] == 2

    async def test_extracts_preferences(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "user_query": "I love AI topic and curiosity hooks",
            "response": "analysis with recommendations",
            "conversation_memory": {"messages": []},
        }
        result = await memory_update_node(state, _make_config(db=db))
        prefs = result["conversation_memory"]["preferences"]
        assert "topic" in prefs
        assert "hook_type" in prefs

    async def test_tracks_recommendation_feedback(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "user_query": "yes that's great, I'll try that",
            "response": "base text\n\n**Recommendations:**\n- try hook A",
            "conversation_memory": {"messages": []},
        }
        result = await memory_update_node(state, _make_config(db=db))
        history = result["conversation_memory"].get("recommendation_history", [])
        assert len(history) == 1
        assert history[0]["feedback"] == "accepted"

    async def test_tracks_recommendation_rejection(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "user_query": "no, that's not what I want",
            "response": "base\n\n**Recommendations:**\n- try this",
            "conversation_memory": {"messages": []},
        }
        result = await memory_update_node(state, _make_config(db=db))
        history = result["conversation_memory"].get("recommendation_history", [])
        assert len(history) == 1
        assert history[0]["feedback"] == "rejected"

    async def test_updates_session_summary(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "user_query": "show me AI tutorial hooks",
            "response": "Your best hook is curiosity.",
            "conversation_memory": {"messages": [], "summary": "Initial summary"},
        }
        result = await memory_update_node(state, _make_config(db=db))
        summary = result["conversation_memory"]["summary"]
        assert "AI" in summary
        assert db.update_session_summary.called

    async def test_preserves_existing_preferences(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "user_query": "show me more tutorials",
            "conversation_memory": {
                "messages": [],
                "preferences": {"topic": "AI", "format": "tutorial"},
            },
        }
        result = await memory_update_node(state, _make_config(db=db))
        prefs = result["conversation_memory"]["preferences"]
        assert prefs["topic"] == "AI"
        assert prefs["format"] == "tutorial"

    async def test_no_feedback_without_recommendations(self) -> None:
        db = AsyncMock()
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})
        db.update_session_summary = AsyncMock(return_value={"id": "s1"})
        state: GraphState = {
            **STATE,
            "user_query": "yes that's good",
            "response": "plain answer without recommendations section",
            "conversation_memory": {"messages": []},
        }
        result = await memory_update_node(state, _make_config(db=db))
        assert "recommendation_history" not in result["conversation_memory"]


class TestGraphRouting:
    def test_route_after_confidence_high(self) -> None:
        state: GraphState = {**STATE, "confidence_score": 0.9}
        assert _route_after_confidence(state) == "conversational_reasoner"

    def test_route_after_confidence_medium(self) -> None:
        state: GraphState = {**STATE, "confidence_score": 0.6}
        assert _route_after_confidence(state) == "set_clarification"

    def test_route_after_confidence_low(self) -> None:
        state: GraphState = {**STATE, "confidence_score": 0.3}
        assert _route_after_confidence(state) == "set_decline"

    def test_route_after_confidence_none(self) -> None:
        state: GraphState = {**STATE, "confidence_score": None}
        assert _route_after_confidence(state) == "set_decline"

    def test_route_after_confidence_boundary_clarify(self) -> None:
        state: GraphState = {**STATE, "confidence_score": CLARIFYING_THRESHOLD}
        assert _route_after_confidence(state) == "set_clarification"

    def test_route_after_confidence_boundary_high(self) -> None:
        state: GraphState = {**STATE, "confidence_score": HIGH_CONFIDENCE_THRESHOLD}
        assert _route_after_confidence(state) == "conversational_reasoner"

    def test_route_after_reasoner_high(self) -> None:
        state: GraphState = {**STATE, "confidence_score": 0.9}
        assert _route_after_reasoner(state) == "recommendation_generator"

    def test_route_after_reasoner_low(self) -> None:
        state: GraphState = {**STATE, "confidence_score": 0.4}
        assert _route_after_reasoner(state) == "citation_builder"

    def test_graph_has_all_nodes(self) -> None:
        g = compiled_graph.get_graph()
        node_names = list(g.nodes.keys())
        assert "conversation_memory" in node_names
        assert "query_understanding" in node_names
        assert "query_transformation" in node_names
        assert "retrieval_planner" in node_names
        assert "parallel_retrieval" in node_names
        assert "context_fusion" in node_names
        assert "confidence_evaluation" in node_names
        assert "conversational_reasoner" in node_names
        assert "recommendation_generator" in node_names
        assert "citation_builder" in node_names
        assert "memory_update" in node_names
        assert "set_decline" in node_names
        assert "set_clarification" in node_names


class TestGraphInvocation:
    async def test_end_to_end_no_db(self) -> None:
        state: GraphState = {**STATE.copy()}
        db = AsyncMock()
        db.get_session = AsyncMock(return_value={"id": "s1", "summary": ""})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.search_reels_hybrid = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})

        result = await compiled_graph.ainvoke(
            state,
            {"configurable": {"db": db, "llm": None}},
        )
        assert result["session_id"] == "test-session"
        assert result["user_query"] == "what should I post next"
        assert result["intent"] is not None
        assert result["rewritten_query"] is not None
        assert result["retrieval_plan"] is not None
        assert result["confidence_score"] is not None
        assert result["response"] is not None
        assert result["citations"] is not None

    async def test_graph_compiles(self) -> None:
        builder = build_conversation_graph()
        graph = builder.compile()
        g = graph.get_graph()
        assert len(g.nodes) == 15

    async def test_high_confidence_flow_includes_recommendations(self) -> None:
        state: GraphState = {**STATE.copy(), "user_query": "analyze my content strategy"}
        db = AsyncMock()
        db.get_session = AsyncMock(return_value={"id": "s1", "summary": ""})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(
            return_value={
                "bestTopics": ["AI"],
                "bestHookTypes": ["CURIOSITY"],
                "bestPostingDay": "Wednesday",
                "audienceInterests": ["tech"],
            }
        )
        db.get_reels_with_metrics = AsyncMock(
            return_value=[{"engagementRate": 0.05, "viralityScore": 2.0, "views": 100, "likes": 10}]
        )
        db.get_competitor_insights_by_niche = AsyncMock(
            return_value=[{"competitorId": "c1", "avgVirality": 2.0}]
        )
        db.search_reels_hybrid = AsyncMock(
            return_value=[{"reel_id": "r1", "retrieval_score": 0.85, "contexts": ["content strategy analysis for reels"]}]
        )
        db.get_trends_by_topic = AsyncMock(
            return_value=[{"topic": "AI trends", "viralityScore": 3.0} for _ in range(12)]
        )
        db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[{"id": "r1", "caption": "content strategy analysis for reels", "topic": "AI", "hookText": "strategy"}]
        )
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})

        result = await compiled_graph.ainvoke(
            state,
            {"configurable": {"db": db, "llm": None}},
        )
        assert result["response"] is not None
        assert "**Recommendations:**" in result["response"]

    async def test_low_confidence_flow_skips_recommendations(self) -> None:
        state: GraphState = {**STATE.copy(), "user_query": "hello"}
        db = AsyncMock()
        db.get_session = AsyncMock(return_value={"id": "s1", "summary": ""})
        db.get_chat_messages = AsyncMock(return_value=[])
        db.get_creator_profile = AsyncMock(return_value=None)
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        db.get_competitor_insights_by_niche = AsyncMock(
            side_effect=lambda niche, **kw: (
                [] if niche == "general" else []
            )
        )
        db.search_reels_hybrid = AsyncMock(return_value=[])
        db.get_trends_by_topic = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(return_value=[])
        db.create_chat_message = AsyncMock(return_value={"id": "m1"})

        result = await compiled_graph.ainvoke(
            state,
            {"configurable": {"db": db, "llm": None}},
        )
        assert result["response"] is not None
        # Low confidence should route to set_decline, skipping recommendations
        assert "**Recommendations:**" not in result["response"]
        assert "couldn't find sufficient evidence" in result["response"].lower()


class TestTools:
    async def test_get_creator_knowledge_found(self) -> None:
        db = AsyncMock()
        db.get_creator_profile = AsyncMock(
            return_value={
                "bestTopics": ["AI"],
                "bestHookTypes": ["CURIOSITY"],
                "bestPostingDay": "Wednesday",
                "audienceInterests": ["tech"],
            }
        )
        result = await get_creator_knowledge(db)
        assert result["best_topics"] == ["AI"]
        assert result["best_hook_types"] == ["CURIOSITY"]

    async def test_get_creator_knowledge_not_found(self) -> None:
        db = AsyncMock()
        db.get_creator_profile = AsyncMock(return_value=None)
        result = await get_creator_knowledge(db)
        assert result == {}

    async def test_get_analytics_empty(self) -> None:
        db = AsyncMock()
        db.get_reels_with_metrics = AsyncMock(return_value=[])
        result = await get_analytics(db)
        assert result["reel_count"] == 0

    async def test_get_analytics_with_data(self) -> None:
        db = AsyncMock()
        db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"engagementRate": 0.05, "viralityScore": 2.0, "views": 100, "likes": 10},
                {"engagementRate": 0.03, "viralityScore": 1.5, "views": 50, "likes": 5},
            ]
        )
        result = await get_analytics(db)
        assert result["reel_count"] == 2
        assert result["avg_engagement_rate"] == 0.04
        assert result["avg_virality_score"] == 1.75
        assert result["total_views"] == 150

    async def test_hybrid_search_no_query(self) -> None:
        db = AsyncMock()
        db.search_reels_hybrid = AsyncMock(return_value=[{"reel_id": "r1"}, {"reel_id": "r2"}])
        result = await hybrid_search(db, query="")
        assert len(result) == 2
        db.search_reels_hybrid.assert_called_once()

    async def test_hybrid_search_with_query_dense(self) -> None:
        db = AsyncMock()
        db.search_reels_hybrid = AsyncMock(
            return_value=[{"reel_id": "r1", "retrieval_score": 0.92, "contexts": ["AI tutorial"]}]
        )
        result = await hybrid_search(db, query="AI tutorial", metadata_filters={"topic": "AI"})
        assert len(result) == 1
        assert result[0]["reel_id"] == "r1"
        db.search_reels_hybrid.assert_called_once()

    async def test_hybrid_search_fallback_keyword(self) -> None:
        db = AsyncMock()
        db.search_reels_hybrid = AsyncMock(return_value=[])
        db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[
                {"id": "r1", "caption": "AI tutorial video", "topic": "AI", "hookText": "learn now"},
                {"id": "r2", "caption": "cooking recipe", "topic": "food", "hookText": "yummy"},
            ]
        )
        result = await hybrid_search(db, query="AI tutorial")
        assert len(result) == 1
        assert result[0]["id"] == "r1"

    async def test_get_competitor_insights_with_niche(self) -> None:
        db = AsyncMock()
        db.get_competitor_insights_by_niche = AsyncMock(
            return_value=[{"competitorId": "c1", "niche": "AI"}]
        )
        result = await get_competitor_insights(db, niche="AI")
        assert len(result) == 1

    async def test_get_competitor_insights_without_niche(self) -> None:
        db = AsyncMock()
        db.get_competitor_insights_by_niche = AsyncMock(
            side_effect=lambda niche, **kw: (
                [] if niche == "general" else [{"competitorId": "c1"}]
            )
        )
        result = await get_competitor_insights(db)
        assert len(result) == 0

    async def test_get_trending_data(self) -> None:
        db = AsyncMock()
        db.get_trends_by_topic = AsyncMock(return_value=[{"topic": "trend1"}])
        result = await get_trending_data(db, topic="AI")
        assert len(result) == 1

    async def test_get_conversation_memory(self) -> None:
        db = AsyncMock()
        db.get_chat_messages = AsyncMock(
            return_value=[{"role": "user", "content": "hi"}]
        )
        db.get_session = AsyncMock(
            return_value={"id": "s1", "summary": "test summary"}
        )
        result = await get_conversation_memory(db, session_id="s1")
        assert result["message_count"] == 1
        assert result["session"]["summary"] == "test summary"


class TestRetrievalFunctions:
    def test_normalize_embedding(self) -> None:
        from app.db import normalize_embedding
        assert normalize_embedding([3.0, 4.0]) == [0.6, 0.8]
        assert normalize_embedding([1.0, 0.0]) == [1.0, 0.0]
        assert normalize_embedding([0.0, 0.0]) == [0.0, 0.0]
        empty: list[float] = []
        assert normalize_embedding(empty) == []

    def test_normalize_embedding_already_normalized(self) -> None:
        from app.db import normalize_embedding
        result = normalize_embedding([0.6, 0.8])
        assert abs(result[0] - 0.6) < 1e-10
        assert abs(result[1] - 0.8) < 1e-10

    def test_build_metadata_clause_no_filters(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause(None)
        assert clause == ""
        assert params == []
        assert needs_ci is False

    def test_build_metadata_clause_empty_filters(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({})
        assert clause == ""
        assert params == []
        assert needs_ci is False

    def test_build_metadata_clause_account_id(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({"account_id": "abc-123"})
        assert "accountId" in clause
        assert params == ["abc-123"]
        assert needs_ci is False

    def test_build_metadata_clause_topic(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({"topic": "AI"})
        assert "ci.\"topic\" ILIKE" in clause
        assert params == ["%AI%"]
        assert needs_ci is True

    def test_build_metadata_clause_topic_and_account(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({"topic": "AI", "account_id": "acc1"})
        assert "accountId" in clause
        assert "topic" in clause
        assert params == ["acc1", "%AI%"]
        assert needs_ci is True

    def test_build_metadata_clause_content_format(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({"content_format": "TUTORIAL"})
        assert "contentFormat" in clause
        assert params == ["TUTORIAL"]
        assert needs_ci is True

    def test_build_metadata_clause_hook_type(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({"hook_type": "CURIOSITY"})
        assert "hookType" in clause
        assert params == ["CURIOSITY"]
        assert needs_ci is True

    def test_build_metadata_clause_full(self) -> None:
        from app.db import _build_metadata_clause
        clause, params, needs_ci = _build_metadata_clause({
            "account_id": "acc1",
            "topic": "AI",
            "content_format": "TUTORIAL",
            "hook_type": "CURIOSITY",
        })
        assert "accountId" in clause
        assert "topic" in clause
        assert "contentFormat" in clause
        assert "hookType" in clause
        assert len(params) == 4
        assert needs_ci is True
        assert " AND " in clause

    def test_parse_time_range_days_last_30(self) -> None:
        from app.db import _parse_time_range_days
        assert _parse_time_range_days("last_30_days") == 30
        assert _parse_time_range_days("last 30 days") == 30
        assert _parse_time_range_days("30d") == 30
        assert _parse_time_range_days("7 days") == 7
        assert _parse_time_range_days("this_week") == 7
        assert _parse_time_range_days("this_month") == 30
        assert _parse_time_range_days("") is None
        assert _parse_time_range_days("invalid") is None

    async def test_search_reels_dense_empty_pool(self) -> None:
        from app.db import DatabaseClient
        db = DatabaseClient("postgresql://fake")
        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await db.search_reels_dense([0.1] * 1536)

    async def test_search_reels_sparse_empty_pool(self) -> None:
        from app.db import DatabaseClient
        db = DatabaseClient("postgresql://fake")
        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await db.search_reels_sparse("test query")

    async def test_search_reels_hybrid_empty_pool(self) -> None:
        from app.db import DatabaseClient
        db = DatabaseClient("postgresql://fake")
        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await db.search_reels_hybrid(query="test", query_embedding=[0.1] * 1536)

    async def test_hybrid_search_with_metadata_filters(self) -> None:
        db = AsyncMock()
        db.search_reels_hybrid = AsyncMock(
            return_value=[{"reel_id": "r1", "retrieval_score": 0.85, "contexts": ["AI content"]}]
        )
        result = await hybrid_search(db, query="AI", metadata_filters={"topic": "AI", "account_id": "acc1"})
        assert len(result) == 1
        db.search_reels_hybrid.assert_called_with(
            query="AI",
            metadata_filters={"topic": "AI", "account_id": "acc1"},
            dense_limit=20,
            sparse_limit=20,
            final_limit=20,
        )

    async def test_hybrid_search_dense_fallback_on_exception(self) -> None:
        db = AsyncMock()
        db.search_reels_hybrid = AsyncMock(side_effect=Exception("DB error"))
        db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[{"id": "r1", "caption": "machine learning", "topic": "AI", "hookText": "learn AI"}]
        )
        result = await hybrid_search(db, query="machine learning")
        assert len(result) == 1
        assert result[0]["id"] == "r1"

    def test_format_retrieval_row(self) -> None:
        from app.db import _format_retrieval_row
        row = type("Row", (), {
            "get": lambda self, k, d=None: {
                "reel_id": "r1", "retrieval_score": 0.85,
                "caption": "hello", "transcript": "world",
                "visual_summary": "summary", "text_overlays": ["text1"],
                "topic": "AI", "hook_text": "hook", "content_format": "TUTORIAL",
                "hook_type": "CURIOSITY", "duration_sec": 30.0,
            }.get(k, d)
        })()
        result = _format_retrieval_row(row)
        assert result["reel_id"] == "r1"
        assert result["retrieval_score"] == 0.85
        assert "hello" in result["contexts"]
        assert "world" in result["contexts"]
        assert result["topic"] == "AI"

    def test_format_sparse_row(self) -> None:
        from app.db import _format_sparse_row
        row = type("Row", (), {
            "get": lambda self, k, d=None: {
                "reel_id": "r2", "bm25_score": 0.75,
                "caption": "AI tutorial", "transcript": "learn AI",
                "visual_summary": None, "text_overlays": [],
                "topic": "AI", "hook_text": "", "content_format": "",
                "hook_type": "", "duration_sec": 45.0,
                "matched_terms": ["AI", "learn"],
            }.get(k, d)
        })()
        result = _format_sparse_row(row)
        assert result["reel_id"] == "r2"
        assert result["bm25_score"] == 0.75
        assert result["matched_terms"] == ["AI", "learn"]
