from __future__ import annotations

import asyncpg
import uuid
from datetime import datetime
from typing import Any
from dateutil import parser as date_parser

from app.reel_bot.config import settings


class ReelBotDatabaseClient:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=1,
                max_size=3,
                statement_cache_size=0,
            )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _ensure_pool(self) -> asyncpg.Pool:
        if not self._pool:
            await self.connect()
        return self._pool

    async def upsert_reels(
        self, handle: str, reels: list[dict[str, Any]]
    ) -> int:
        """Upsert reels for a handle. Returns count of upserted reels."""
        pool = await self._ensure_pool()
        count = 0
        now = datetime.now()

        async with pool.acquire() as conn:
            for reel in reels:
                reel_id = str(uuid.uuid4())
                posted_at = reel.get("posted_at")
                if posted_at and isinstance(posted_at, str):
                    try:
                        posted_at = date_parser.isoparse(posted_at)
                    except (ValueError, TypeError):
                        posted_at = None

                await conn.execute(
                    """
                    INSERT INTO "ReelBotReel" (
                        "id", "instagramHandle", "instagramReelId", "videoUrl", "permalink", "caption",
                        "views", "likes", "commentsCount", "shares", "durationSec",
                        "postedAt", "rawTranscript", "cleanTranscript", "wordCount",
                        "wpm", "topKeywords", "createdAt", "updatedAt"
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                    ON CONFLICT ("instagramHandle", "instagramReelId") DO UPDATE SET
                        "views" = $7,
                        "likes" = $8,
                        "commentsCount" = $9,
                        "shares" = $10,
                        "permalink" = $5,
                        "rawTranscript" = $13,
                        "cleanTranscript" = $14,
                        "wordCount" = $15,
                        "wpm" = $16,
                        "topKeywords" = $17,
                        "updatedAt" = $19
                    """,
                    reel_id,
                    handle,
                    reel["instagram_reel_id"],
                    reel["video_url"],
                    reel.get("permalink"),
                    reel.get("caption"),
                    reel.get("views", 0),
                    reel.get("likes", 0),
                    reel.get("comments_count", 0),
                    reel.get("shares", 0),
                    reel.get("duration_sec"),
                    posted_at,
                    reel.get("raw_transcript"),
                    reel.get("clean_transcript"),
                    reel.get("word_count"),
                    reel.get("wpm"),
                    reel.get("top_keywords", []),
                    now,
                    now,
                )
                count += 1

        return count

    async def get_reels_freshness(self, handle: str) -> datetime | None:
        """Most recent updatedAt across this handle's stored reels, or None if
        never ingested. Used to skip a live Hiker re-fetch when data is still
        fresh - each ingest call spends real Hiker API credits."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                'SELECT MAX("updatedAt") FROM "ReelBotReel" WHERE "instagramHandle" = $1',
                handle,
            )

    async def get_recent_reels(self, handle: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch recent reels for a handle."""
        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    "instagramReelId", "videoUrl", "permalink", "caption", "views", "likes",
                    "commentsCount", "shares", "durationSec", "postedAt",
                    "rawTranscript", "cleanTranscript", "wordCount", "wpm", "topKeywords"
                FROM "ReelBotReel"
                WHERE "instagramHandle" = $1
                ORDER BY "postedAt" DESC
                LIMIT $2
                """,
                handle,
                limit,
            )

        return [dict(row) for row in rows]

    async def create_session(self, handle: str) -> str:
        """Create a new chat session, return session_id."""
        pool = await self._ensure_pool()
        session_id = str(uuid.uuid4())
        now = datetime.now()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "ReelBotSession" ("id", "instagramHandle", "createdAt", "updatedAt")
                VALUES ($1, $2, $3, $4)
                """,
                session_id,
                handle,
                now,
                now,
            )

        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session metadata."""
        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT "id", "instagramHandle", "createdAt", "updatedAt" FROM "ReelBotSession" WHERE "id" = $1',
                session_id,
            )

        return dict(row) if row else None

    async def append_message(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Append a message to a session."""
        pool = await self._ensure_pool()
        message_id = str(uuid.uuid4())
        now = datetime.now()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "ReelBotChatMessage" ("id", "sessionId", "role", "content", "createdAt")
                VALUES ($1, $2, $3, $4, $5)
                """,
                message_id,
                session_id,
                role,
                content,
                now,
            )

    async def get_recent_messages(
        self, session_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fetch recent messages from a session."""
        pool = await self._ensure_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT "role", "content", "createdAt"
                FROM "ReelBotChatMessage"
                WHERE "sessionId" = $1
                ORDER BY "createdAt" ASC
                LIMIT $2
                """,
                session_id,
                limit,
            )

        return [dict(row) for row in rows]
