from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from app.reel_bot.config import settings
from app.reel_bot.reel_chat_engine import ReelChatEngine
from app.reel_bot.reel_cleaner import clean_and_analyze
from app.reel_bot.reel_db import ReelBotDatabaseClient
from app.reel_bot.reel_hiker_client import (
    HikerError,
    HikerAuthError,
    HikerInsufficientFundsError,
    ReelBotHikerClient,
)
from app.reel_bot.reel_llm_client import LLMError, ReelBotLLMClient
from app.reel_bot.reel_models import (
    ReelChatRequest,
    ReelChatResponse,
    ReelIngestPayload,
    ReelIngestResponse,
    ReelChatMessage,
    ReelSessionListResponse,
    ReelSessionMessagesResponse,
    ReelSessionSummary,
)
from app.reel_bot.reel_whisper import transcribe_reel
from app.logging_setup import get_logger

logger = get_logger(__name__)


router = APIRouter(prefix="/reel-bot", tags=["reel-bot"])

_db: ReelBotDatabaseClient | None = None
_llm: ReelBotLLMClient | None = None
_hiker: ReelBotHikerClient | None = None


async def _get_db() -> ReelBotDatabaseClient:
    global _db
    if _db is None:
        _db = ReelBotDatabaseClient()
        await _db.connect()
    return _db


async def _get_llm() -> ReelBotLLMClient:
    global _llm
    if _llm is None:
        _llm = ReelBotLLMClient()
    return _llm


async def _get_hiker() -> ReelBotHikerClient:
    global _hiker
    if _hiker is None:
        _hiker = ReelBotHikerClient()
    return _hiker


async def _process_single_reel(media: dict[str, Any]) -> dict[str, Any] | None:
    """Process a single reel: extract data, transcribe, clean. Returns reel_data dict or None."""
    try:
        instagram_reel_id = str(media.get("pk", ""))
        shortcode = media.get("code", "")
        permalink = f"https://www.instagram.com/reel/{shortcode}/" if shortcode else ""
        video_url = ""

        video_versions = media.get("video_versions") or []
        if video_versions:
            best = max(video_versions, key=lambda v: v.get("bandwidth") or 0)
            video_url = best.get("url", "")

        caption_obj = media.get("caption")
        caption = caption_obj.get("text") if isinstance(caption_obj, dict) else None

        duration_sec = media.get("video_duration", 0.0)
        posted_at_timestamp = media.get("taken_at")
        posted_at = None
        if posted_at_timestamp:
            posted_at = datetime.fromtimestamp(posted_at_timestamp).isoformat()

        views = int(media.get("play_count", 0))
        likes = int(media.get("like_count", 0))
        comments_count = int(media.get("comment_count", 0))
        shares = int(media.get("reshare_count", 0))

        raw_transcript = None
        clean_transcript = None
        word_count = None
        wpm = None
        top_keywords = []

        if video_url:
            transcript_result = await transcribe_reel(video_url, instagram_reel_id)
            if transcript_result:
                raw_transcript = transcript_result.get("transcript")
                if raw_transcript and duration_sec > 0:
                    analysis = clean_and_analyze(raw_transcript, duration_sec)
                    clean_transcript = analysis["clean_transcript"]
                    word_count = analysis["word_count"]
                    wpm = analysis["wpm"]
                    top_keywords = analysis["top_keywords"]

        return {
            "instagram_reel_id": instagram_reel_id,
            "video_url": video_url,
            "permalink": permalink,
            "caption": caption,
            "views": views,
            "likes": likes,
            "comments_count": comments_count,
            "shares": shares,
            "duration_sec": duration_sec,
            "posted_at": posted_at,
            "raw_transcript": raw_transcript,
            "clean_transcript": clean_transcript,
            "word_count": word_count,
            "wpm": wpm,
            "top_keywords": top_keywords,
        }
    except Exception:
        return None


@router.post("/ingest", response_model=ReelIngestResponse)
async def ingest_reels(
    payload: ReelIngestPayload,
) -> ReelIngestResponse:
    """Ingest latest reels from an Instagram handle."""
    handle = payload.instagram_handle.lstrip("@").lower()

    if not handle:
        raise HTTPException(status_code=400, detail="Invalid Instagram handle")

    try:
        db = await _get_db()

        last_updated = await db.get_reels_freshness(handle)
        if last_updated is not None:
            age_hours = (datetime.now() - last_updated).total_seconds() / 3600
            if age_hours < settings.cache_hours:
                cached_reels = await db.get_recent_reels(handle, limit=settings.max_reels)
                wpm_values = [r["wpm"] for r in cached_reels if r.get("wpm")]
                avg_wpm = (
                    round(sum(wpm_values) / len(wpm_values), 2) if wpm_values else None
                )
                all_keywords = []
                for reel in cached_reels:
                    all_keywords.extend(reel.get("topKeywords") or [])
                unique_keywords = list(dict.fromkeys(all_keywords))[:5]

                logger.info(
                    "reel_bot_ingest_cache_hit",
                    handle=handle,
                    age_hours=round(age_hours, 1),
                    reels=len(cached_reels),
                )
                return ReelIngestResponse(
                    instagram_handle=handle,
                    reels_synced=len(cached_reels),
                    avg_wpm=avg_wpm,
                    top_keywords=unique_keywords,
                )

        hiker = await _get_hiker()

        user_data = await hiker.fetch_user_by_username(handle)
        if not user_data or not user_data.get("pk"):
            raise HTTPException(
                status_code=404,
                detail=f"Instagram handle '{handle}' not found or is private",
            )

        user_id = str(user_data.get("pk"))

        media_items = await hiker.fetch_user_clips_all(
            user_id, max_items=settings.max_reels
        )

        tasks = [_process_single_reel(media) for media in media_items]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        stored_reels = [r for r in results if r is not None]
        wpm_values = [r["wpm"] for r in stored_reels if r.get("wpm")]

        if not stored_reels:
            raise HTTPException(
                status_code=500,
                detail="No reels could be processed for this account",
            )

        await db.upsert_reels(handle, stored_reels)

        avg_wpm = (
            round(sum(wpm_values) / len(wpm_values), 2) if wpm_values else None
        )

        all_keywords = []
        for reel in stored_reels:
            all_keywords.extend(reel.get("top_keywords", []))

        unique_keywords = list(dict.fromkeys(all_keywords))[:5]

        return ReelIngestResponse(
            instagram_handle=handle,
            reels_synced=len(stored_reels),
            avg_wpm=avg_wpm,
            top_keywords=unique_keywords,
        )

    except HikerAuthError:
        raise HTTPException(
            status_code=401, detail="Invalid Hiker API token"
        )
    except HikerInsufficientFundsError:
        raise HTTPException(
            status_code=402, detail="Hiker API credits exhausted"
        )
    except HikerError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ReelChatResponse)
async def chat(
    payload: ReelChatRequest,
) -> ReelChatResponse:
    """Chat about a creator's reels."""
    handle = payload.instagram_handle.lstrip("@").lower()
    session_id = payload.session_id
    user_message = payload.message

    if not handle:
        raise HTTPException(status_code=400, detail="Invalid Instagram handle")

    if not user_message or not user_message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        db = await _get_db()
        llm = await _get_llm()

        if not session_id:
            session_id = await db.create_session(handle)

        engine = ReelChatEngine(db, llm)
        response = await engine.run(session_id, handle, user_message)

        return ReelChatResponse(session_id=session_id, response=response)

    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=ReelSessionListResponse)
async def list_sessions(instagram_handle: str) -> ReelSessionListResponse:
    """Recent chat sessions for a handle, for a sidebar history list."""
    handle = instagram_handle.lstrip("@").lower()
    if not handle:
        raise HTTPException(status_code=400, detail="Invalid Instagram handle")

    db = await _get_db()
    rows = await db.list_sessions(handle)

    return ReelSessionListResponse(
        sessions=[
            ReelSessionSummary(
                session_id=row["session_id"],
                updated_at=row["updatedAt"].isoformat(),
                preview=row["preview"][:80],
            )
            for row in rows
        ]
    )


@router.get("/sessions/{session_id}/messages", response_model=ReelSessionMessagesResponse)
async def get_session_messages(session_id: str) -> ReelSessionMessagesResponse:
    """Full message history for one session (for switching back to a past chat)."""
    db = await _get_db()
    session = await db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = await db.get_recent_messages(session_id, limit=200)
    return ReelSessionMessagesResponse(
        session_id=session_id,
        messages=[ReelChatMessage(role=r["role"], content=r["content"]) for r in rows],
    )
