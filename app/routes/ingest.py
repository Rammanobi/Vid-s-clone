from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.monitoring import db_queries_total
from app.pipeline import PipelineStage, run_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestAccountRequest(BaseModel):
    username: str
    max_reels: int = 10


@router.post("/account")
async def ingest_account(
    body: IngestAccountRequest,
    db: DatabaseClient = Depends(get_db_dependency),
    user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Real end-to-end ingestion: fetches the account + reels from HikerAPI,
    stores them, then runs analytics/intelligence/knowledge against the
    result. This is the actual on-ramp for "give me a username" - it was
    previously a raw manual-insert stub that the frontend's `{username}`
    call had never actually been able to satisfy (it required instagram_id
    and follower counts the caller could not know in advance)."""
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    username = body.username.strip().lstrip("@")
    if not username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="username is required")

    from hiker_ingestion.client import (
        HikerAPIError,
        HikerAuthError,
        HikerClient,
        HikerInsufficientFundsError,
        HikerNotFoundError,
    )
    from hiker_ingestion.config import settings as hiker_settings
    from hiker_ingestion.db import DatabaseClient as HikerDatabaseClient
    from hiker_ingestion.orchestrator import IngestionOrchestrator

    hiker_client = HikerClient()
    hiker_db = HikerDatabaseClient(hiker_settings.database_url)
    try:
        await hiker_db.connect()
        orchestrator = IngestionOrchestrator(hiker_client, hiker_db)
        try:
            await orchestrator.ingest_creator(
                username=username, max_reels=body.max_reels, max_comments=50
            )
        except HikerAuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        except HikerNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instagram user '{username}' not found",
            ) from exc
        except HikerInsufficientFundsError as exc:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
        except HikerAPIError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    finally:
        await hiker_db.close()
        await hiker_client.close()

    account = await db.get_account_by_username(username)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ingestion completed but the account could not be found afterward",
        )

    reels = await db.get_reels_by_account(account["id"], limit=1000)

    pipeline_result = await run_pipeline(
        db,
        stages=[PipelineStage.ANALYTICS, PipelineStage.INTELLIGENCE, PipelineStage.KNOWLEDGE],
        analytics_limit=1000,
        intelligence_limit=1000,
        intelligence_use_llm=False,
        knowledge_account_id=account["id"],
        knowledge_limit=1000,
    )

    db_queries_total.labels(operation="ingest_account").inc()
    logger.info(
        "account_ingested",
        username=username,
        account_id=account["id"],
        reels_ingested=len(reels),
        pipeline_status=pipeline_result.status,
    )

    return {
        "status": "ok",
        "account_id": account["id"],
        "username": username,
        "reels_ingested": len(reels),
        "pipeline_status": pipeline_result.status,
    }


@router.get("/account/{username}")
async def get_account(
    username: str,
    db: DatabaseClient = Depends(get_db_dependency),
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
    db: DatabaseClient = Depends(get_db_dependency),
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
    db: DatabaseClient = Depends(get_db_dependency),
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