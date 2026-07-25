from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

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
    reranker_node,
    retrieval_planner_node,
    set_clarification_node,
    set_decline_node,
)
from app.graph.state import GraphState

CLARIFYING_THRESHOLD = 0.5
HIGH_CONFIDENCE_THRESHOLD = 0.8

NODE_CONVERSATION_MEMORY = "conversation_memory"
NODE_QUERY_UNDERSTANDING = "query_understanding"
NODE_QUERY_TRANSFORMATION = "query_transformation"
NODE_RETRIEVAL_PLANNER = "retrieval_planner"
NODE_PARALLEL_RETRIEVAL = "parallel_retrieval"
NODE_RERANKER = "reranker"
NODE_CONTEXT_FUSION = "context_fusion"
NODE_CONFIDENCE_EVALUATION = "confidence_evaluation"
NODE_CONVERSATIONAL_REASONER = "conversational_reasoner"
NODE_RECOMMENDATION_GENERATOR = "recommendation_generator"
NODE_CITATION_BUILDER = "citation_builder"
NODE_MEMORY_UPDATE = "memory_update"
NODE_SET_DECLINE = "set_decline"
NODE_SET_CLARIFICATION = "set_clarification"


def _route_after_confidence(
    state: GraphState,
) -> Literal["conversational_reasoner", "set_clarification", "set_decline"]:
    confidence = state.get("confidence_score") or 0.0
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return NODE_CONVERSATIONAL_REASONER
    if confidence >= CLARIFYING_THRESHOLD:
        return NODE_SET_CLARIFICATION
    return NODE_SET_DECLINE


def _route_after_reasoner(
    state: GraphState,
) -> Literal["recommendation_generator", "citation_builder"]:
    confidence = state.get("confidence_score") or 0.0
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return NODE_RECOMMENDATION_GENERATOR
    return NODE_CITATION_BUILDER


def build_conversation_graph() -> StateGraph:
    builder = StateGraph(GraphState)

    builder.add_node(NODE_CONVERSATION_MEMORY, conversation_memory_node)
    builder.add_node(NODE_QUERY_UNDERSTANDING, query_understanding_node)
    builder.add_node(NODE_QUERY_TRANSFORMATION, query_transformation_node)
    builder.add_node(NODE_RETRIEVAL_PLANNER, retrieval_planner_node)
    builder.add_node(NODE_PARALLEL_RETRIEVAL, parallel_retrieval_node)
    builder.add_node(NODE_RERANKER, reranker_node)
    builder.add_node(NODE_CONTEXT_FUSION, context_fusion_node)
    builder.add_node(NODE_CONFIDENCE_EVALUATION, confidence_evaluation_node)
    builder.add_node(NODE_CONVERSATIONAL_REASONER, conversational_reasoner_node)
    builder.add_node(NODE_RECOMMENDATION_GENERATOR, recommendation_generator_node)
    builder.add_node(NODE_CITATION_BUILDER, citation_builder_node)
    builder.add_node(NODE_MEMORY_UPDATE, memory_update_node)
    builder.add_node(NODE_SET_DECLINE, set_decline_node)
    builder.add_node(NODE_SET_CLARIFICATION, set_clarification_node)

    builder.set_entry_point(NODE_CONVERSATION_MEMORY)

    builder.add_edge(NODE_CONVERSATION_MEMORY, NODE_QUERY_UNDERSTANDING)
    builder.add_edge(NODE_QUERY_UNDERSTANDING, NODE_QUERY_TRANSFORMATION)
    builder.add_edge(NODE_QUERY_TRANSFORMATION, NODE_RETRIEVAL_PLANNER)
    builder.add_edge(NODE_RETRIEVAL_PLANNER, NODE_PARALLEL_RETRIEVAL)
    builder.add_edge(NODE_PARALLEL_RETRIEVAL, NODE_RERANKER)
    builder.add_edge(NODE_RERANKER, NODE_CONTEXT_FUSION)
    builder.add_edge(NODE_CONTEXT_FUSION, NODE_CONFIDENCE_EVALUATION)

    builder.add_conditional_edges(
        NODE_CONFIDENCE_EVALUATION,
        _route_after_confidence,
    )

    builder.add_conditional_edges(
        NODE_CONVERSATIONAL_REASONER,
        _route_after_reasoner,
    )

    builder.add_edge(NODE_SET_DECLINE, NODE_CITATION_BUILDER)
    builder.add_edge(NODE_SET_CLARIFICATION, NODE_CITATION_BUILDER)
    builder.add_edge(NODE_RECOMMENDATION_GENERATOR, NODE_CITATION_BUILDER)
    builder.add_edge(NODE_CITATION_BUILDER, NODE_MEMORY_UPDATE)
    builder.add_edge(NODE_MEMORY_UPDATE, END)

    return builder


conversation_graph = build_conversation_graph()
compiled_graph = conversation_graph.compile()
