from __future__ import annotations

import asyncio
import os
from typing import Any

from hiker_ingestion.client import HikerClient
from hiker_ingestion.config import settings
from hiker_ingestion.db import DatabaseClient
from hiker_ingestion.logging_setup import configure_logging, get_logger
from hiker_ingestion.mapper import (
    _coerce_id,
    _safe_int,
    is_reel,
    map_account,
    map_account_snapshot,
    map_comment,
    map_metric,
    map_reel,
    unwrap_clips,
    unwrap_user,
)
from hiker_ingestion.monitoring import (
    accounts_fetched,
    comments_fetched,
    last_successful_fetch,
    metrics_stored,
    reels_fetched,
    start_metrics_server,
)

logger = get_logger(__name__)


class IngestionOrchestrator:
    def __init__(
        self,
        hiker_client: HikerClient,
        db_client: DatabaseClient,
    ) -> None:
        self.hiker = hiker_client
        self.db = db_client

    async def ingest_account(
        self, user: dict[str, Any], is_competitor: bool = False
    ) -> str | None:
        """Takes the ALREADY-UNWRAPPED profile object (the `user` value), not the
        raw response. Reading `pk` off the raw response root is what left
        instagram_id empty and aborted every ingestion run."""
        account_data = map_account(user)
        account_data.is_competitor = is_competitor
        logger.info("ingesting_account", username=account_data.username)

        db_id = await self.db.upsert_account(account_data)

        if db_id:
            snapshot = map_account_snapshot(account_data)
            await self.db.insert_account_snapshot(snapshot, db_id)
            accounts_fetched.inc()
            last_successful_fetch.labels(data_type="account").set_to_current_time()
            logger.info(
                "account_ingested",
                username=account_data.username,
                db_id=db_id,
                follower_count=account_data.follower_count,
            )

        return db_id

    async def ingest_reels(
        self,
        instagram_id: str,
        account_db_id: str,
        follower_count: int = 0,
        max_reels: int = 50,
        max_comments: int = 200,
    ) -> None:
        logger.info(
            "ingesting_reels",
            instagram_id=instagram_id,
            max_reels=max_reels,
        )

        raw_items = await self.hiker.fetch_user_clips_all(
            instagram_id, max_items=max_reels
        )
        # The client returns raw `response.items` elements, each shaped
        # {"media": {...}}. Re-wrap so the single tested unwrapper owns the
        # double-nesting rule rather than duplicating it here.
        clips = unwrap_clips({"response": {"items": raw_items}})

        for clip in clips:
            try:
                if not is_reel(clip):
                    logger.debug(
                        "skipping_non_reel",
                        product_type=clip.get("product_type"),
                        media_type=clip.get("media_type"),
                    )
                    continue

                reel_data = map_reel(clip, account_db_id)
                reel_db_id = await self.db.upsert_reel(reel_data)

                if reel_db_id:
                    reels_fetched.inc()

                    metric_data = map_metric(
                        clip, reel_db_id, follower_count
                    )
                    await self.db.upsert_reel_metric(metric_data)
                    metrics_stored.inc()

                    # /v2/media/comments expects the COMPOSITE id
                    # "{media_pk}_{owner_pk}" — confirmed by the recorded call
                    # log (entries 5/9/13/17/21), and it equals media["id"].
                    media_pk = _coerce_id(clip.get("pk"))
                    composite_id = clip.get("id") or (
                        f"{media_pk}_{instagram_id}" if media_pk else ""
                    )
                    if composite_id:
                        await self.ingest_comments(
                            composite_id,
                            reel_db_id,
                            instagram_id,
                            max_comments=max_comments,
                        )

                    last_successful_fetch.labels(
                        data_type="reel"
                    ).set_to_current_time()

            except Exception:
                logger.exception(
                    "failed_to_process_reel",
                    instagram_reel_id=clip.get("pk", clip.get("id", "unknown")),
                )

    async def ingest_comments(
        self,
        media_id: str,
        reel_db_id: str,
        creator_instagram_id: str | None = None,
        max_comments: int = 200,
    ) -> None:
        logger.debug(
            "ingesting_comments",
            media_id=media_id,
            max_comments=max_comments,
        )

        try:
            raw_comments = await self.hiker.fetch_media_comments_all(
                media_id, max_comments=max_comments
            )
        except Exception:
            logger.exception(
                "failed_to_fetch_comments", media_id=media_id
            )
            return

        for raw_comment in raw_comments:
            try:
                comment_data = map_comment(
                    raw_comment, reel_db_id, creator_instagram_id
                )
                await self.db.insert_comment(comment_data)
                comments_fetched.inc()
            except Exception:
                logger.exception(
                    "failed_to_process_comment",
                    comment_id=raw_comment.get("pk", "unknown"),
                )

        last_successful_fetch.labels(data_type="comment").set_to_current_time()
        logger.debug(
            "comments_ingested",
            media_id=media_id,
            count=len(raw_comments),
        )

    async def ingest_creator(
        self,
        username: str,
        max_reels: int = 50,
        max_comments: int = 200,
    ) -> None:
        logger.info(
            "ingesting_creator",
            username=username,
            max_reels=max_reels,
        )

        # Fetch once, unwrap once — the old code called fetch_user_by_username
        # twice (once inside ingest_account, once here) and read `pk` off the
        # raw response root both times, which is empty because the profile is
        # nested under "user".
        raw_response = await self.hiker.fetch_user_by_username(username)
        user = unwrap_user(raw_response)
        instagram_id = _coerce_id(user.get("pk"))
        follower_count = _safe_int(user.get("follower_count"), 0)

        if not instagram_id:
            logger.error("missing_instagram_id", username=username)
            return

        db_id = await self.ingest_account(user, is_competitor=False)
        if not db_id:
            logger.error("failed_to_create_account", username=username)
            return

        await self.ingest_reels(
            instagram_id=instagram_id,
            account_db_id=db_id,
            follower_count=follower_count,
            max_reels=max_reels,
            max_comments=max_comments,
        )

        logger.info(
            "creator_ingestion_complete",
            username=username,
        )


async def main() -> None:
    configure_logging()
    start_metrics_server()

    hiker_client = HikerClient()
    db_client = DatabaseClient(settings.database_url)

    try:
        await db_client.connect()

        orchestrator = IngestionOrchestrator(hiker_client, db_client)

        usernames = [
            u.strip()
            for u in os.environ.get("HIKER_USERNAMES", "").split(",")
            if u.strip()
        ]

        if not usernames:
            logger.warning(
                "no_usernames_configured",
                hint="Set HIKER_USERNAMES env var (comma-separated)",
            )
            return

        for username in usernames:
            await orchestrator.ingest_creator(
                username=username,
                max_reels=int(os.environ.get("HIKER_MAX_REELS", "50")),
                max_comments=int(os.environ.get("HIKER_MAX_COMMENTS", "200")),
            )

    finally:
        await hiker_client.close()
        await db_client.close()


if __name__ == "__main__":
    asyncio.run(main())