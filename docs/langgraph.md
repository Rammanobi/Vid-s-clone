# LangGraph Agent

The AI agent is a `StateGraph` with 13 nodes, 2 conditional routing decisions, and 6 sequential edges.

## GraphState Schema (`app/graph/state.py`)

```python
class GraphState(TypedDict):
    session_id: str                                  # Current session ID
    user_query: str                                  # Original user message
    rewritten_query: str | None                      # LLM-optimized search query
    intent: dict[str, Any] | None                    # {intent_type, topic, metric, time_range, comparison_type}
    metadata_filters: dict[str, Any] | None          # Filters for hybrid search
    retrieval_plan: list[dict[str, Any]] | None       # Ordered list of source queries to execute
    creator_context: dict[str, Any] | None           # CreatorProfile data
    analytics_context: dict[str, Any] | None         # ReelMetrics aggregated data
    competitor_context: dict[str, Any] | None        # CompetitorInsight data
    retrieved_documents: list[dict[str, Any]] | None # Raw documents from parallel_retrieval
    ranked_context: dict[str, Any] | None            # Fused + reranked + combined context
    confidence_score: float | None                   # 0.0–1.0 confidence metric
    evidence: dict[str, Any] | None                  # Provenance tracking
    response: str | None                             # Generated answer
    citations: list[dict[str, Any]] | None           # [{source, type, summary}]
    conversation_memory: dict[str, Any] | None        # {session, messages, message_count, preferences, summary}
```

## Node Responsibilities

| Node | File | Function | Responsibility |
|------|------|----------|-------------|
| `conversation_memory` | `nodes.py:64` | `conversation_memory_node` | Load chat history + session summary from DB |
| `query_understanding` | `nodes.py:79` | `query_understanding_node` | LLM intent extraction + keyword-based fallback |
| `query_transformation` | `nodes.py:133` | `query_transformation_node` | LLM query rewrite + intent-context fallback |
| `retrieval_planner` | `nodes.py:168` | `retrieval_planner_node` | Build source plan based on intent_type |
| `parallel_retrieval` | `nodes.py:260` | `parallel_retrieval_node` | Execute all sources concurrently via ToolRegistry |
| `reranker` | `nodes.py:346` | `reranker_node` | Merge, dedup, rerank, compute retrieval confidence |
| `context_fusion` | `nodes.py:380` | `context_fusion_node` | Assemble all context into ranked_context dict |
| `confidence_evaluation` | `nodes.py:436` | `confidence_evaluation_node` | Compute overall confidence from sources + documents |
| `set_decline` | `nodes.py:483` | `set_decline_node` | Return "insufficient evidence" response |
| `set_clarification` | `nodes.py:496` | `set_clarification_node` | Return partial answer + clarification prompt |
| `conversational_reasoner` | `nodes.py:512` | `conversational_reasoner_node` | LLM reasoning from evidence (high confidence path) |
| `recommendation_generator` | `nodes.py:564` | `recommendation_generator_node` | LLM-generate actionable recommendations |
| `citation_builder` | `nodes.py:611` | `citation_builder_node` | Build provenance citations from all context sources |
| `memory_update` | `nodes.py:710` | `memory_update_node` | Persist messages, update summary, extract preferences |

## Conditional Routing

### After Confidence Evaluation

```python
def _route_after_confidence(state: GraphState):
    confidence = state.get("confidence_score") or 0.0
    if confidence >= 0.8:
        return "conversational_reasoner"   # Full reasoning
    if confidence >= 0.5:
        return "set_clarification"          # Partial answer + clarification
    return "set_decline"                    # Decline to answer
```

### After Conversational Reasoner

```python
def _route_after_reasoner(state: GraphState):
    confidence = state.get("confidence_score") or 0.0
    if confidence >= 0.8:
        return "recommendation_generator"   # Add recommendations
    return "citation_builder"               # Just citations, no recommendations
```

## Tool Registry (`app/graph/registry.py`)

Singleton `ToolRegistry` with 5 registered tools:

```python
registry.register(ToolInfo(
    name="creator_knowledge",
    description="Creator's best topics, hooks, posting patterns, and audience interests",
    func=get_creator_knowledge,
    read_only=True,
    param_names=["account_id"],
))
registry.register(ToolInfo(
    name="analytics",
    description="Performance metrics: engagement rate, virality score, views, likes across reels",
    func=get_analytics,
    read_only=True,
    param_names=["limit"],
))
registry.register(ToolInfo(
    name="hybrid_search",
    description="Semantic and keyword search across reel transcripts, captions, visual summary...",
    func=hybrid_search,
    read_only=True,
    param_names=["query", "metadata_filters", "limit"],
))
registry.register(ToolInfo(
    name="competitor",
    description="Competitor strategies, winning formats, top topics, and virality benchmarks by niche",
    func=get_competitor_insights,
    read_only=True,
    param_names=["niche", "limit"],
))
registry.register(ToolInfo(
    name="trends",
    description="Trending topics, hook patterns, content formats sorted by virality score",
    func=get_trending_data,
    read_only=True,
    param_names=["topic", "limit"],
))
```

## Source-to-Context Mapping

```python
# Structured context sources → dict keys
SOURCE_TO_CONTEXT_KEY = {
    "creator_knowledge": "creator_context",
    "analytics": "analytics_context",
    "competitor": "competitor_context",
}

# Document sources → retain in retrieved_documents list
SOURCE_TO_DOC_SOURCES = {
    "trends": "trends",
    "hybrid_search": "hybrid_search",
}
```

## Intent-to-Plan Mapping

| Intent Type | Sources Queried |
|-------------|----------------|
| `content_strategy` | creator_knowledge, analytics, trends, competitor |
| `performance_analysis` | analytics, creator_knowledge |
| `recommendation` | creator_knowledge, trends, competitor, hybrid_search |
| `trend_discovery` | trends, competitor, hybrid_search |
| `competitor_analysis` | competitor, trends, hybrid_search |
| `general` | creator_knowledge, analytics, hybrid_search |

## Memory Update Details

The `memory_update_node` does the following:

1. **Preference extraction**: Scans user query for keywords like "topic", "hook", "format", "monday" etc.
2. **Feedback detection**: Detects acceptance/rejection of previous recommendations via keywords ("yes" → accepted, "no"/"not" → rejected)
3. **Message persistence**: Writes user + assistant messages to DB via `create_chat_message`
4. **Summary update**: Concatenates existing summary, preferences, query snippet, response preview (max 1000 chars)
5. **Recommendation history**: Appends accepted/rejected recommendations for future context

## Fallback Reasoning

When LLM is unavailable or errors, the agent uses deterministic fallbacks:

```python
_fallback_reasoning():  # Template-based response from analytics + creator + competitor + trends
_fallback_recommendations():  # Best topics, best hooks, trending topics
```
