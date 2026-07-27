from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.graph.graph import compiled_graph
from app.graph.state import GraphState
from app.logging_setup import get_logger
from app.monitoring import (
    agent_confidence_bucket,
    agent_errors_total,
    agent_invocation_duration_seconds,
    agent_invocations_total,
    db_queries_total,
)
from app.llm import LLMClient
from app.on_demand_enrichment import ensure_reels_transcribed

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    session_id: str
    message: str
    reel_count: int | None = None


class CitationItem(BaseModel):
    source: str
    type: str
    summary: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    citations: list[CitationItem] = []
    confidence_score: float | None = None
    intent: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    elapsed_sec: float | None = None
    transcription_status: list[dict[str, Any]] | None = None


def _build_initial_state(
    session_id: str,
    message: str,
    pinned_transcripts: list[dict[str, Any]] | None = None,
) -> GraphState:
    return {
        "session_id": session_id,
        "user_query": message,
        "rewritten_query": None,
        "intent": None,
        "metadata_filters": None,
        "retrieval_plan": None,
        "creator_context": None,
        "analytics_context": None,
        "competitor_context": None,
        "retrieved_documents": None,
        "pinned_transcripts": pinned_transcripts,
        "ranked_context": None,
        "confidence_score": None,
        "evidence": None,
        "response": None,
        "citations": None,
        "conversation_memory": None,
    }


async def _invoke_graph(
    session_id: str,
    message: str,
    db: DatabaseClient,
    llm: LLMClient | None,
    pinned_transcripts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    initial = _build_initial_state(session_id, message, pinned_transcripts)

    try:
        result = await compiled_graph.ainvoke(
            initial,
            {"configurable": {"db": db, "llm": llm}},
        )
        elapsed = time.monotonic() - start
        agent_invocations_total.labels(mode="sync").inc()
        agent_invocation_duration_seconds.labels(mode="sync").observe(elapsed)

        confidence = result.get("confidence_score") or 0.0
        if confidence >= 0.8:
            agent_confidence_bucket.labels(bucket="high").set(1)
            agent_confidence_bucket.labels(bucket="medium").set(0)
            agent_confidence_bucket.labels(bucket="low").set(0)
        elif confidence >= 0.5:
            agent_confidence_bucket.labels(bucket="high").set(0)
            agent_confidence_bucket.labels(bucket="medium").set(1)
            agent_confidence_bucket.labels(bucket="low").set(0)
        else:
            agent_confidence_bucket.labels(bucket="high").set(0)
            agent_confidence_bucket.labels(bucket="medium").set(0)
            agent_confidence_bucket.labels(bucket="low").set(1)

        return result
    except RuntimeError as exc:
        elapsed = time.monotonic() - start
        agent_errors_total.labels(mode="sync").inc()
        agent_invocation_duration_seconds.labels(mode="sync").observe(elapsed)
        logger.error("graph_db_access_failed", error=str(exc), elapsed_sec=round(elapsed, 3))
        return {
            "response": "Service temporarily unavailable. Please try again later.",
            "citations": [],
            "confidence_score": 0.0,
            "intent": None,
            "evidence": None,
        }
    except Exception as exc:
        elapsed = time.monotonic() - start
        agent_errors_total.labels(mode="sync").inc()
        agent_invocation_duration_seconds.labels(mode="sync").observe(elapsed)
        logger.error("graph_invocation_failed", error=str(exc), elapsed_sec=round(elapsed, 3))
        raise


async def _validate_session(
    session_id: str,
    user: str,
    db: DatabaseClient,
) -> dict[str, Any]:
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.get("userId") != user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    db_queries_total.labels(operation="agent_chat").inc()
    return session


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    body: ChatRequest,
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> ChatResponse:
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available")

    await _validate_session(body.session_id, user, db)

    transcription_status: list[dict[str, Any]] | None = None
    pinned_transcripts: list[dict[str, Any]] | None = None
    if body.reel_count and body.reel_count > 0:
        try:
            transcription_status = await ensure_reels_transcribed(db, body.reel_count)
            logger.info(
                "on_demand_transcription_batch_complete",
                requested=body.reel_count,
                processed=len(transcription_status),
            )
            # Pin these reels' transcripts directly into the graph state instead
            # of letting them compete for a slot in hybrid_search's ranking -
            # the user explicitly asked for these N reels to be analyzed, so
            # their transcript must be guaranteed context, not "hopefully
            # retrieved" (dense/embedding search never even sees them until a
            # full pipeline re-run recomputes their embedding).
            pinned_transcripts = [
                {
                    "instagram_reel_id": item.get("instagram_reel_id"),
                    "transcript": item.get("transcript"),
                }
                for item in transcription_status
                if item.get("transcript") and not item.get("error")
            ] or None
        except Exception as exc:
            logger.warning("on_demand_transcription_batch_failed", error=str(exc))

    start = time.monotonic()
    llm = LLMClient()
    result = await _invoke_graph(body.session_id, body.message, db, llm, pinned_transcripts)
    elapsed = time.monotonic() - start

    raw_citations = result.get("citations") or []
    return ChatResponse(
        session_id=body.session_id,
        response=result.get("response") or "",
        citations=[CitationItem(**c) for c in raw_citations],
        confidence_score=result.get("confidence_score"),
        intent=result.get("intent"),
        evidence=result.get("evidence"),
        elapsed_sec=round(elapsed, 3),
        transcription_status=transcription_status,
    )


@router.post("/chat/stream", response_model=None)
async def agent_chat_stream(
    body: ChatRequest,
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> StreamingResponse:
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available")

    await _validate_session(body.session_id, user, db)

    async def _event_stream() -> AsyncGenerator[str, None]:
        llm = LLMClient()
        start = time.monotonic()

        yield f"data: {json.dumps({'event': 'start', 'session_id': body.session_id})}\n\n"

        try:
            result = await _invoke_graph(body.session_id, body.message, db, llm)
            elapsed = time.monotonic() - start

            raw_citations = result.get("citations") or []
            payload = {
                "event": "complete",
                "session_id": body.session_id,
                "response": result.get("response") or "",
                "citations": [{"source": c["source"], "type": c["type"], "summary": c["summary"]} for c in raw_citations],
                "confidence_score": result.get("confidence_score"),
                "intent": result.get("intent"),
                "evidence": result.get("evidence"),
                "elapsed_sec": round(elapsed, 3),
            }
            yield f"data: {json.dumps(payload)}\n\n"
        except Exception as exc:
            logger.error("stream_chat_failed", error=str(exc))
            yield f"data: {json.dumps({'event': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.websocket("/ws")
async def agent_websocket(
    websocket: WebSocket,
    db: DatabaseClient = Depends(get_db_dependency),
):
    # SECURITY FIX: Require authentication BEFORE accepting connection
    # This prevents unauthenticated connections from being held open (DoS vector)
    user: str | None = None
    try:
        # Client must send auth token in first message before any other messages
        initial_data = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=5.0,  # 5 second timeout for auth message
        )
        token = initial_data.get("token", "")

        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return

        # Verify token BEFORE accepting connection
        from app.auth import verify_token

        try:
            payload = verify_token(token)
            user = payload.get("sub")
            if not isinstance(user, str) or not user:
                await websocket.close(code=1008, reason="Invalid token")
                return
        except Exception as exc:
            logger.warning("websocket_auth_failed", error=str(exc))
            await websocket.close(code=1008, reason="Authentication failed")
            return
    except asyncio.TimeoutError:
        await websocket.close(code=1008, reason="Authentication timeout")
        return
    except Exception as exc:
        logger.error("websocket_initial_receive_failed", error=str(exc))
        await websocket.close(code=1011, reason="Connection error")
        return

    # NOW accept connection after successful authentication
    await websocket.accept()

    if db is None:
        await websocket.send_json({"event": "error", "detail": "Database not available"})
        await websocket.close(code=1011)
        return

    llm = LLMClient()

    try:
        while True:
            data = await websocket.receive_json()
            session_id = data.get("session_id", "")
            message = data.get("message", "")

            # Authentication already verified at connection time
            # User identity is already established as 'user'

            session = await db.get_session(session_id)
            if not session or session.get("userId") != user:
                await websocket.send_json({"event": "error", "detail": "Session not found or unauthorized"})
                continue

            db_queries_total.labels(operation="agent_ws_chat").inc()
            await websocket.send_json({"event": "start", "session_id": session_id})

            try:
                result = await _invoke_graph(session_id, message, db, llm)
                raw_citations = result.get("citations") or []
                await websocket.send_json({
                    "event": "complete",
                    "session_id": session_id,
                    "response": result.get("response") or "",
                    "citations": [{"source": c["source"], "type": c["type"], "summary": c["summary"]} for c in raw_citations],
                    "confidence_score": result.get("confidence_score"),
                    "intent": result.get("intent"),
                    "evidence": result.get("evidence"),
                })
            except Exception as exc:
                logger.error("ws_graph_invocation_failed", error=str(exc))
                agent_errors_total.labels(mode="ws").inc()
                await websocket.send_json({"event": "error", "detail": "Failed to process message"})

    except WebSocketDisconnect:
        logger.debug("websocket_disconnected")
    except Exception as exc:
        logger.error("websocket_error", error=str(exc))


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
