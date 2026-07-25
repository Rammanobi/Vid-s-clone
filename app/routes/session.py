from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.cache import cache_delete, cache_get, cache_set
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import db_queries_total

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("")
async def create_session(
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    session = await db.create_session(user_id=user)
    db_queries_total.labels(operation="create_session").inc()

    logger.info("session_created", session_id=session["id"], user=user)
    return session


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    cache_key = f"session:{session_id}"
    cached = await cache_get(cache_key)
    if cached:
        if cached.get("userId") != user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session",
            )
        return cached

    session = await db.get_session(session_id)
    db_queries_total.labels(operation="get_session").inc()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session["userId"] != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )

    await cache_set(cache_key, session, ttl=300)

    return session


@router.get("")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    cache_key = f"sessions:list:{user}:{limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sessions = await db.get_sessions_by_user(user, limit=limit)
    db_queries_total.labels(operation="list_sessions").inc()

    result = {"sessions": sessions, "count": len(sessions)}
    await cache_set(cache_key, result, ttl=120)

    return result


@router.put("/{session_id}/summary")
async def update_session_summary(
    session_id: str,
    summary: str,
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if session["userId"] != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this session",
        )

    updated = await db.update_session_summary(session_id, summary)
    db_queries_total.labels(operation="update_session_summary").inc()

    await cache_delete(f"session:{session_id}")

    return {"status": "ok", "session": updated}


@router.post("/{session_id}/messages")
async def add_chat_message(
    session_id: str,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if session["userId"] != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this session",
        )

    message = await db.create_chat_message(session_id, role, content, citations)
    db_queries_total.labels(operation="create_message").inc()

    return {"status": "ok", "message": message}


@router.get("/{session_id}/messages")
async def get_chat_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if session["userId"] != user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    messages = await db.get_chat_messages(session_id, limit=limit)
    db_queries_total.labels(operation="get_messages").inc()

    return {"messages": messages, "count": len(messages)}