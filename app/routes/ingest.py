from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.monitoring import db_queries_total, http_request_duration_seconds, http_requests_total

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/account")
async def ingest_account(
    instagram_id: str,
    username: str,
    follower_count: int = 0,
    following_count: int = 0,
    posts_count: int = 0,
    is_competitor: bool = False,
    db: DatabaseClient = Depends(lambda: None),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    result = await db.ingest_account(
        instagram_id=instagram_id,
        username=username,
        follower_count=follower_count,
        following_count=following_count,
        posts_count=posts_count,
        is_competitor=is_competitor,
    )
    db_queries_total.labels(operation="ingest_account").inc()

    logger.info(
        "account_ingested",
        instagram_id=instagram_id,
        username=username,
    )

    return {"status": "ok", "account": result}


@router.get("/account/{username}")
async def get_account(
    username: str,
    db: DatabaseClient = Depends(lambda: None),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    account = await db.get_account_by_username(username)
    db_queries_total.labels(operation="get_account").inc()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{username}' not found",
        )

    return account


@router.get("/account/{account_id}/reels")
async def get_account_reels(
    account_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DatabaseClient = Depends(lambda: None),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    reels = await db.get_reels_by_account(account_id, limit=limit, offset=offset)
    db_queries_total.labels(operation="get_reels").inc()

    return {"reels": reels, "limit": limit, "offset": offset, "count": len(reels)}


@router.get("/reel/{instagram_reel_id}")
async def get_reel(
    instagram_reel_id: str,
    db: DatabaseClient = Depends(lambda: None),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    reel = await db.get_reel_by_instagram_id(instagram_reel_id)
    db_queries_total.labels(operation="get_reel").inc()

    if not reel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reel '{instagram_reel_id}' not found",
        )

    return reel