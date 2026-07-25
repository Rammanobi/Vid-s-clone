from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import DatabaseClient
from app.graph.graph import compiled_graph
from app.graph.state import GraphState
from app.logging_setup import get_logger
from app.monitoring import db_queries_total
from app.llm import LLMClient

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    citations: list[dict[str, Any]] = []
    confidence_score: float | None = None
    intent: dict[str, Any] | None = None


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    body: ChatRequest,
    db: DatabaseClient = Depends(lambda: None),
    user: str = Depends(get_current_user),
) -> ChatResponse:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    session = await db.get_session(body.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if session.get("userId") != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )

    db_queries_total.labels(operation="agent_chat").inc()

    initial_state: GraphState = {
        "session_id": body.session_id,
        "user_query": body.message,
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

    llm = LLMClient()

    try:
        result = await compiled_graph.ainvoke(
            initial_state,
            {"configurable": {"db": db, "llm": llm}},
        )
    except Exception as exc:
        logger.error("graph_invocation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message",
        )

    return ChatResponse(
        session_id=body.session_id,
        response=result.get("response") or "",
        citations=result.get("citations") or [],
        confidence_score=result.get("confidence_score"),
        intent=result.get("intent"),
    )


@router.get("/graph")
async def get_graph_info() -> dict[str, Any]:
    g = compiled_graph.get_graph()
    return {
        "nodes": list(g.nodes.keys()),
        "edges": [
            {"source": e.source, "target": e.target, "conditional": e.conditional}
            for e in g.edges
        ],
    }
