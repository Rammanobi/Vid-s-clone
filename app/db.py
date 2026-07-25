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

    async def update_reel_transcript(
        self,
        reel_db_id: str,
        transcript: str,
        transcript_json: list[dict[str, Any]],
    ) -> None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            await conn.execute(
                'UPDATE "Reel" SET "transcript" = $1, "transcriptJson" = $2::jsonb WHERE "id" = $3',
                transcript,
                json.dumps(transcript_json),
                reel_db_id,
            )
        logger.debug("reel_transcript_updated", reel_id=reel_db_id)

    async def update_reel_text_overlays(
        self,
        reel_db_id: str,
        text_overlays: list[str],
    ) -> None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            await conn.execute(
                'UPDATE "Reel" SET "textOverlays" = $1 WHERE "id" = $2',
                text_overlays,
                reel_db_id,
            )
        logger.debug(
            "reel_text_overlays_updated",
            reel_id=reel_db_id,
            count=len(text_overlays),
        )

    async def get_reels_pending_enrichment(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT "id", "instagramReelId", "videoUrl" FROM "Reel" '
                'WHERE "transcript" IS NULL OR "textOverlays" = \'{}\''
                "ORDER BY \"createdAt\" ASC LIMIT $1",
                limit,
            )
            return [dict(r) for r in rows]

    async def update_reel_visual_features(
        self,
        reel_db_id: str,
        embedding: list[float],
        visual_topics: list[str],
        visual_summary: str,
    ) -> None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            await conn.execute(
                'UPDATE "Reel" SET '
                '"combinedEmbedding" = $1::vector, '
                '"visualTopics" = $2, '
                '"visualSummary" = $3 '
                'WHERE "id" = $4',
                embedding,
                visual_topics,
                visual_summary,
                reel_db_id,
            )
        logger.debug(
            "reel_visual_features_updated",
            reel_id=reel_db_id,
            topics_count=len(visual_topics),
        )

    async def upsert_content_intelligence(
        self,
        reel_db_id: str,
        topic: str | None = None,
        hook_type: str | None = None,
        hook_text: str | None = None,
        cta: str | None = None,
        content_format: str | None = None,
        teaching_style: str | None = None,
        narrative_style: str | None = None,
        audience_intent: str | None = None,
        sentiment: str | None = None,
        visual_style: str | None = None,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO "ContentIntelligence" (
                    "reelId", "topic", "hookType", "hookText", "cta",
                    "contentFormat", "teachingStyle", "narrativeStyle",
                    "audienceIntent", "sentiment", "visualStyle"
                ) VALUES ($1, $2, $3::"HookType", $4, $5, $6::"ContentFormat",
                          $7, $8, $9, $10, $11)
                ON CONFLICT ("reelId")
                DO UPDATE SET
                    "topic" = EXCLUDED."topic",
                    "hookType" = EXCLUDED."hookType",
                    "hookText" = EXCLUDED."hookText",
                    "cta" = EXCLUDED."cta",
                    "contentFormat" = EXCLUDED."contentFormat",
                    "teachingStyle" = EXCLUDED."teachingStyle",
                    "narrativeStyle" = EXCLUDED."narrativeStyle",
                    "audienceIntent" = EXCLUDED."audienceIntent",
                    "sentiment" = EXCLUDED."sentiment",
                    "visualStyle" = EXCLUDED."visualStyle"
                RETURNING "id", "reelId", "topic", "hookType"
                """,
                reel_db_id,
                topic,
                hook_type,
                hook_text,
                cta,
                content_format,
                teaching_style,
                narrative_style,
                audience_intent,
                sentiment,
                visual_style,
            )
            result = dict(row) if row else None
            if result:
                logger.debug(
                    "content_intelligence_upserted",
                    reel_id=reel_db_id,
                    topic=topic,
                )
            return result

    async def upsert_reel_metrics(
        self,
        reel_db_id: str,
        views: int = 0,
        likes: int = 0,
        comments_count: int = 0,
        saves: int | None = None,
        shares: int | None = None,
        reach: int | None = None,
        engagement_rate: float = 0.0,
        save_rate: float | None = None,
        share_rate: float | None = None,
        comment_rate: float | None = None,
        virality_score: float = 1.0,
        view_to_follower: float = 0.0,
        metric_quality: str = "FULL",
        is_volatile: bool = False,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO "ReelMetric" (
                    "reelId", "views", "likes", "commentsCount",
                    "saves", "shares", "reach",
                    "engagementRate", "saveRate", "shareRate",
                    "commentRate", "viralityScore", "viewToFollower",
                    "metricQuality", "isVolatile"
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7,
                    $8, $9, $10, $11, $12, $13,
                    $14::"MetricQuality", $15
                )
                ON CONFLICT ("reelId")
                DO UPDATE SET
                    "views" = EXCLUDED."views",
                    "likes" = EXCLUDED."likes",
                    "commentsCount" = EXCLUDED."commentsCount",
                    "saves" = EXCLUDED."saves",
                    "shares" = EXCLUDED."shares",
                    "reach" = EXCLUDED."reach",
                    "engagementRate" = EXCLUDED."engagementRate",
                    "saveRate" = EXCLUDED."saveRate",
                    "shareRate" = EXCLUDED."shareRate",
                    "commentRate" = EXCLUDED."commentRate",
                    "viralityScore" = EXCLUDED."viralityScore",
                    "viewToFollower" = EXCLUDED."viewToFollower",
                    "metricQuality" = EXCLUDED."metricQuality",
                    "isVolatile" = EXCLUDED."isVolatile"
                RETURNING "id", "reelId", "engagementRate", "viralityScore"
                """,
                reel_db_id,
                views,
                likes,
                comments_count,
                saves,
                shares,
                reach,
                engagement_rate,
                save_rate,
                share_rate,
                comment_rate,
                virality_score,
                view_to_follower,
                metric_quality,
                is_volatile,
            )
            result = dict(row) if row else None
            if result:
                logger.debug(
                    "reel_metrics_upserted",
                    reel_id=reel_db_id,
                    engagement_rate=engagement_rate,
                    virality_score=virality_score,
                )
            return result

    async def insert_reel_snapshot(
        self,
        reel_db_id: str,
        views: int = 0,
        likes: int = 0,
        comments_count: int = 0,
        saves: int | None = None,
        shares: int | None = None,
        reach: int | None = None,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO "ReelSnapshot" (
                    "reelId", "views", "likes", "commentsCount",
                    "saves", "shares", "reach"
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING "id", "reelId", "snapshotAt"
                """,
                reel_db_id,
                views,
                likes,
                comments_count,
                saves,
                shares,
                reach,
            )
            result = dict(row) if row else None
            if result:
                logger.debug(
                    "reel_snapshot_inserted",
                    reel_id=reel_db_id,
                    snapshot_id=result["id"],
                )
            return result

    async def get_reel_snapshots(
        self,
        reel_db_id: str,
        limit: int = 30,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM "ReelSnapshot" WHERE "reelId" = $1 '
                'ORDER BY "snapshotAt" DESC LIMIT $2 OFFSET $3',
                reel_db_id,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    async def get_reels_with_metrics(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r."id", r."instagramReelId", r."videoUrl",
                       r."views", r."likes", r."commentsCount",
                       r."saves", r."shares", r."reach",
                       r."durationSec", r."postedAt",
                       a."followerCount", a."postsCount"
                FROM "Reel" r
                JOIN "Account" a ON r."accountId" = a."id"
                ORDER BY r."postedAt" DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            return [dict(r) for r in rows]

    async def get_reel_metrics(
        self,
        reel_db_id: str,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "ReelMetric" WHERE "reelId" = $1',
                reel_db_id,
            )
            return dict(row) if row else None

    async def get_reel_count(self) -> int:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            return await conn.fetchval('SELECT COUNT(*) FROM "Reel"')

    async def upsert_creator_profile(
        self,
        account_id: str,
        best_topics: list[str] | None = None,
        worst_topics: list[str] | None = None,
        best_hook_types: list[str] | None = None,
        best_posting_day: str | None = None,
        best_duration_range: str | None = None,
        best_content_format: str | None = None,
        audience_interests: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            best_hooks_pg = best_hook_types if best_hook_types else []
            interests_pg = audience_interests if audience_interests else []
            row = await conn.fetchrow(
                """
                INSERT INTO "CreatorProfile" (
                    "accountId", "bestTopics", "worstTopics",
                    "bestHookTypes", "bestPostingDay", "bestDurationRange",
                    "bestContentFormat", "audienceInterests"
                ) VALUES ($1, $2, $3, $4::"HookType"[], $5, $6, $7::"ContentFormat", $8)
                ON CONFLICT ("accountId")
                DO UPDATE SET
                    "bestTopics" = $2,
                    "worstTopics" = $3,
                    "bestHookTypes" = $4::"HookType"[],
                    "bestPostingDay" = $5,
                    "bestDurationRange" = $6,
                    "bestContentFormat" = $7::"ContentFormat",
                    "audienceInterests" = $8
                RETURNING "id", "accountId", "bestTopics", "bestHookTypes"
                """,
                account_id,
                best_topics or [],
                worst_topics or [],
                best_hooks_pg,
                best_posting_day,
                best_duration_range,
                best_content_format,
                interests_pg,
            )
            result = dict(row) if row else None
            if result:
                logger.debug(
                    "creator_profile_upserted",
                    account_id=account_id,
                    best_topics_count=len(best_topics or []),
                )
            return result

    async def get_creator_profile(
        self,
        account_id: str,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM "CreatorProfile" WHERE "accountId" = $1',
                account_id,
            )
            return dict(row) if row else None

    async def upsert_competitor_insight(
        self,
        competitor_id: str,
        niche: str,
        winning_format: str | None = None,
        top_topics: list[str] | None = None,
        avg_virality: float = 1.0,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO "CompetitorInsight" (
                    "competitorId", "niche", "winningFormat",
                    "topTopics", "avgVirality"
                ) VALUES ($1, $2, $3::"ContentFormat", $4, $5)
                ON CONFLICT ("competitorId", "niche")
                DO UPDATE SET
                    "winningFormat" = $3::"ContentFormat",
                    "topTopics" = $4,
                    "avgVirality" = $5
                RETURNING "id", "competitorId", "niche", "avgVirality"
                """,
                competitor_id,
                niche,
                winning_format,
                top_topics or [],
                avg_virality,
            )
            return dict(row) if row else None

    async def get_competitor_insights_by_niche(
        self,
        niche: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM "CompetitorInsight" '
                'WHERE "niche" = $1 ORDER BY "avgVirality" DESC LIMIT $2',
                niche,
                limit,
            )
            return [dict(r) for r in rows]

    async def upsert_trend_store(
        self,
        topic: str,
        hook_pattern: str | None = None,
        content_format: str | None = None,
        virality_score: float = 1.0,
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO "TrendStore" (
                    "topic", "hookPattern", "contentFormat", "viralityScore"
                ) VALUES ($1, $2, $3::"ContentFormat", $4)
                ON CONFLICT ("topic", "hookPattern")
                DO UPDATE SET
                    "contentFormat" = $3::"ContentFormat",
                    "viralityScore" = $4
                RETURNING "id", "topic", "viralityScore"
                """,
                topic,
                hook_pattern,
                content_format,
                virality_score,
            )
            return dict(row) if row else None

    async def get_trends_by_topic(
        self,
        topic: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            if topic:
                rows = await conn.fetch(
                    'SELECT * FROM "TrendStore" WHERE "topic" = $1 '
                    'ORDER BY "viralityScore" DESC LIMIT $2',
                    topic,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    'SELECT * FROM "TrendStore" '
                    'ORDER BY "viralityScore" DESC LIMIT $1',
                    limit,
                )
            return [dict(r) for r in rows]

    async def get_reels_with_full_intelligence(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r."id", r."instagramReelId", r."videoUrl",
                       r."views", r."likes", r."commentsCount",
                       r."saves", r."shares", r."reach",
                       r."durationSec", r."postedAt",
                       r."caption", r."transcript",
                       a."followerCount", a."postsCount",
                       rm."engagementRate", rm."viralityScore",
                       ci."topic", ci."hookType", ci."hookText",
                       ci."cta", ci."contentFormat",
                       ci."narrativeStyle", ci."audienceIntent",
                       ci."sentiment"
                FROM "Reel" r
                JOIN "Account" a ON r."accountId" = a."id"
                LEFT JOIN "ReelMetric" rm ON rm."reelId" = r."id"
                LEFT JOIN "ContentIntelligence" ci ON ci."reelId" = r."id"
                ORDER BY r."postedAt" DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            return [dict(r) for r in rows]