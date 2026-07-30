from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import DatabaseClient
from app.deps import get_db_dependency
from app.logging_setup import get_logger
from app.prompts import PROMPT_KEYS, prompt_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/prompts", tags=["admin"])


class PromptUpdate(BaseModel):
    content: str


@router.get("")
async def list_prompts(
    _user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Current effective value of every prompt, and whether it's coming from
    the database, an env var, or the built-in default."""
    return {"prompts": prompt_cache.as_dict()}


@router.put("/{key}")
async def update_prompt(
    key: str,
    body: PromptUpdate,
    db: DatabaseClient = Depends(get_db_dependency),
    _user: str = Depends(get_current_user),
) -> dict[str, Any]:
    if key not in PROMPT_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown prompt key. Valid keys: {', '.join(PROMPT_KEYS)}",
        )
    if not body.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prompt content cannot be blank.",
        )
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable.",
        )

    row = await db.upsert_prompt(key, body.content)
    await prompt_cache.refresh(db)
    logger.info("prompt_updated", key=key)
    return {"key": row["key"], "content": row["content"], "updatedAt": str(row["updatedAt"])}
