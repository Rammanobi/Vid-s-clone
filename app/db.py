from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg

from app.logging_setup import get_logger

logger = get_logger(__name__)


class DatabaseClient:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=2, max_size=10
        )
        logger.info("db_pool_created")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("db_pool_closed")

    async def health(self) -> bool:
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    async def get_account_by_username(
        self, username: str
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "Account" WHERE "username" = $1',
                username,
            )
            return dict(row) if row else None

    async def get_reels_by_account(
        self, account_id: str, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM "Reel" WHERE "accountId" = $1 '
                "ORDER BY \"postedAt\" DESC LIMIT $2 OFFSET $3",
                account_id,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    async def get_reel_by_instagram_id(
        self, instagram_reel_id: str
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "Reel" WHERE "instagramReelId" = $1',
                instagram_reel_id,
            )
            return dict(row) if row else None

    async def create_session(
        self, user_id: str
    ) -> dict[str, Any]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'INSERT INTO "Session" ("userId") VALUES ($1) '
                'RETURNING "id", "userId", "createdAt", "updatedAt"',
                user_id,
            )
            return dict(row)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "Session" WHERE "id" = $1',
                session_id,
            )
            return dict(row) if row else None

    async def get_sessions_by_user(
        self, user_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT "id", "userId", "summary", "createdAt", "updatedAt" '
                'FROM "Session" WHERE "userId" = $1 '
                "ORDER BY \"createdAt\" DESC LIMIT $2",
                user_id,
                limit,
            )
            return [dict(r) for r in rows]

    async def update_session_summary(
        self, session_id: str, summary: str
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'UPDATE "Session" SET "summary" = $1 WHERE "id" = $2 '
                'RETURNING "id", "userId", "summary", "createdAt", "updatedAt"',
                summary,
                session_id,
            )
            return dict(row) if row else None

    async def create_chat_message(
        self, session_id: str, role: str, content: str, citations: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'INSERT INTO "ChatMessage" ("sessionId", "role", "content", "citations") '
                "VALUES ($1, $2, $3, $4::jsonb) "
                'RETURNING "id", "sessionId", "role", "content", "createdAt"',
                session_id,
                role,
                content,
                json.dumps(citations) if citations else None,
            )
            return dict(row)

    async def get_chat_messages(
        self, session_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM "ChatMessage" WHERE "sessionId" = $1 '
                "ORDER BY \"createdAt\" ASC LIMIT $2",
                session_id,
                limit,
            )
            return [dict(r) for r in rows]

    async def ingest_account(
        self, instagram_id: str, username: str, follower_count: int = 0,
        following_count: int = 0, posts_count: int = 0, is_competitor: bool = False
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO "Account" (
                    "instagramId", "username", "followerCount",
                    "followingCount", "postsCount", "isCompetitor"
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT ("instagramId")
                DO UPDATE SET
                    "username" = EXCLUDED."username",
                    "followerCount" = EXCLUDED."followerCount",
                    "followingCount" = EXCLUDED."followingCount",
                    "postsCount" = EXCLUDED."postsCount"
                RETURNING "id", "instagramId", "username", "followerCount"
                """,
                instagram_id, username, follower_count,
                following_count, posts_count, is_competitor,
            )
            return dict(row) if row else None