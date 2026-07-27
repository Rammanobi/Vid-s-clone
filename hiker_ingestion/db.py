from __future__ import annotations

import time
from typing import Any

import asyncpg

from hiker_ingestion.logging_setup import get_logger
from hiker_ingestion.models import (
    AccountData,
    AccountSnapshotData,
    CommentData,
    ReelData,
    ReelMetricData,
)
from hiker_ingestion.monitoring import db_insert_duration_seconds

logger = get_logger(__name__)


class DatabaseClient:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=1,
            max_size=10,
            # Same PgBouncer transaction-mode requirement as app/db.py - the
            # earlier live ingestion test likely only worked by luck since
            # each query pattern was mostly unique to its own connection.
            statement_cache_size=0,
        )
        logger.info("database_pool_created")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("database_pool_closed")

    async def _execute(
        self, query: str, *args: Any, table: str = "unknown"
    ) -> str | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        start = time.monotonic()
        async with self._pool.acquire() as conn:
            result = await conn.fetchval(query, *args)
        duration = time.monotonic() - start

        db_insert_duration_seconds.labels(table=table).observe(duration)
        return result

    async def upsert_account(self, account: AccountData) -> str | None:
        query = """
            INSERT INTO "Account" (
                "instagramId", "username", "followerCount",
                "followingCount", "postsCount", "isCompetitor",
                "fullName", "biography", "profilePicUrl",
                "isVerified", "isPrivate", "externalUrl"
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT ("instagramId")
            DO UPDATE SET
                "username" = EXCLUDED."username",
                "followerCount" = EXCLUDED."followerCount",
                "followingCount" = EXCLUDED."followingCount",
                "postsCount" = EXCLUDED."postsCount",
                "isCompetitor" = EXCLUDED."isCompetitor",
                "fullName" = EXCLUDED."fullName",
                "biography" = EXCLUDED."biography",
                "profilePicUrl" = EXCLUDED."profilePicUrl",
                "isVerified" = EXCLUDED."isVerified",
                "isPrivate" = EXCLUDED."isPrivate",
                "externalUrl" = EXCLUDED."externalUrl"
            RETURNING "id"
        """
        return await self._execute(
            query,
            account.instagram_id,
            account.username,
            account.follower_count,
            account.following_count,
            account.posts_count,
            account.is_competitor,
            account.full_name,
            account.biography,
            account.profile_pic_url,
            account.is_verified,
            account.is_private,
            account.external_url,
            table="Account",
        )

    async def upsert_reel(self, reel: ReelData) -> str | None:
        query = """
            INSERT INTO "Reel" (
                "accountId", "instagramReelId", "videoUrl",
                "caption", "durationSec", "postedAt",
                "transcript", "transcriptJson",
                "visualTopics", "textOverlays", "visualSummary"
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT ("instagramReelId")
            DO UPDATE SET
                "videoUrl" = EXCLUDED."videoUrl",
                "caption" = EXCLUDED."caption",
                "durationSec" = EXCLUDED."durationSec",
                "transcript" = EXCLUDED."transcript",
                "transcriptJson" = EXCLUDED."transcriptJson",
                "visualTopics" = EXCLUDED."visualTopics",
                "textOverlays" = EXCLUDED."textOverlays",
                "visualSummary" = EXCLUDED."visualSummary"
            RETURNING "id"
        """
        return await self._execute(
            query,
            reel.account_id,
            reel.instagram_reel_id,
            reel.video_url,
            reel.caption,
            reel.duration_sec,
            reel.posted_at,
            reel.transcript,
            reel.transcript_json,
            reel.visual_topics,
            reel.text_overlays,
            reel.visual_summary,
            table="Reel",
        )

    async def upsert_reel_metric(self, metric: ReelMetricData) -> str | None:
        query = """
            INSERT INTO "ReelMetric" (
                "reelId", "views", "likes", "commentsCount",
                "saves", "shares",
                "engagementRate", "saveRate", "shareRate", "commentRate",
                "viralityScore", "viewToFollower",
                "metricQuality", "isVolatile"
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT ("reelId")
            DO UPDATE SET
                "views" = EXCLUDED."views",
                "likes" = EXCLUDED."likes",
                "commentsCount" = EXCLUDED."commentsCount",
                "saves" = EXCLUDED."saves",
                "shares" = EXCLUDED."shares",
                "engagementRate" = EXCLUDED."engagementRate",
                "saveRate" = EXCLUDED."saveRate",
                "shareRate" = EXCLUDED."shareRate",
                "commentRate" = EXCLUDED."commentRate",
                "viralityScore" = EXCLUDED."viralityScore",
                "viewToFollower" = EXCLUDED."viewToFollower",
                "metricQuality" = EXCLUDED."metricQuality"::"MetricQuality",
                "isVolatile" = EXCLUDED."isVolatile"
            RETURNING "id"
        """
        return await self._execute(
            query,
            metric.reel_id,
            metric.views,
            metric.likes,
            metric.comments_count,
            metric.saves,
            metric.shares,
            metric.engagement_rate,
            metric.save_rate,
            metric.share_rate,
            metric.comment_rate,
            metric.virality_score,
            metric.view_to_follower,
            metric.metric_quality.value,
            metric.is_volatile,
            table="ReelMetric",
        )

    async def insert_comment(self, comment: CommentData) -> str | None:
        query = """
            INSERT INTO "Comment" (
                "reelId", "authorId", "text", "isCreator", "postedAt"
            ) VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
            RETURNING "id"
        """
        return await self._execute(
            query,
            comment.reel_id,
            comment.author_id,
            comment.text,
            comment.is_creator,
            comment.posted_at,
            table="Comment",
        )

    async def insert_account_snapshot(
        self, snapshot: AccountSnapshotData, account_db_id: str
    ) -> str | None:
        query = """
            INSERT INTO "AccountSnapshot" (
                "accountId", "followerCount"
            ) VALUES ($1, $2)
            RETURNING "id"
        """
        return await self._execute(
            query,
            account_db_id,
            snapshot.follower_count,
            table="AccountSnapshot",
        )

    async def get_account_by_instagram_id(
        self, instagram_id: str
    ) -> dict[str, Any] | None:
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT "id", "instagramId", "followerCount" FROM "Account" WHERE "instagramId" = $1',
                instagram_id,
            )
            if row:
                return dict(row)
            return None