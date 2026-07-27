from __future__ import annotations

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
)
from app.reel_bot.reel_whisper import transcribe_reel


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


@router.post("/ingest", response_model=ReelIngestResponse)
async def ingest_reels(
    payload: ReelIngestPayload,
) -> ReelIngestResponse:
    """Ingest latest reels from an Instagram handle."""
    handle = payload.instagram_handle.lstrip("@").lower()

    if not handle:
        raise HTTPException(status_code=400, detail="Invalid Instagram handle")

    try:
        hiker = await _get_hiker()
        db = await _get_db()

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

        stored_reels = []
        wpm_values = []

        for media in media_items:
            try:
                instagram_reel_id = str(media.get("pk", ""))
                video_url = ""

                video_versions = media.get("video_versions") or []
                if video_versions:
                    best = max(
                        video_versions, key=lambda v: v.get("bandwidth") or 0
                    )
                    video_url = best.get("url", "")

                caption_obj = media.get("caption")
                caption = (
                    caption_obj.get("text")
                    if isinstance(caption_obj, dict)
                    else None
                )

                duration_sec = media.get("video_duration", 0.0)
                posted_at_timestamp = media.get("taken_at")
                posted_at = None
                if posted_at_timestamp:
                    posted_at = datetime.fromtimestamp(
                        posted_at_timestamp
                    ).isoformat()

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
                    transcript_result = await transcribe_reel(
                        video_url, instagram_reel_id
                    )
                    if transcript_result:
                        raw_transcript = transcript_result.get("transcript")
                        if raw_transcript and duration_sec > 0:
                            analysis = clean_and_analyze(
                                raw_transcript, duration_sec
                            )
                            clean_transcript = analysis["clean_transcript"]
                            word_count = analysis["word_count"]
                            wpm = analysis["wpm"]
                            top_keywords = analysis["top_keywords"]

                            wpm_values.append(wpm)

                reel_data = {
                    "instagram_reel_id": instagram_reel_id,
                    "video_url": video_url,
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
                stored_reels.append(reel_data)

            except Exception as e:
                continue

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
