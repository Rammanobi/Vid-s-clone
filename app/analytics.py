from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import DatabaseClient
from app.logging_setup import get_logger
from app.metrics import ReelMetricsResult, compute_reel_metrics
from app.monitoring import db_queries_total

logger = get_logger(__name__)

EARLY_LIFECYCLE_HOURS = 24
LATE_LIFECYCLE_DAYS = 7


async def process_single_reel(
    reel: dict[str, Any],
    db: DatabaseClient,
) -> ReelMetricsResult:
    reel_id: str = reel["id"]

    metrics = compute_reel_metrics(
        reel_id=reel_id,
        views=reel.get("views", 0) or 0,
        likes=reel.get("likes", 0) or 0,
        comments_count=reel.get("commentsCount", 0) or 0,
        saves=reel.get("saves"),
        shares=reel.get("shares"),
        reach=reel.get("reach"),
        follower_count=reel.get("followerCount"),
        prev_follower_count=reel.get("prevFollowerCount"),
        duration_sec=reel.get("durationSec"),
        posts_count=reel.get("postsCount"),
        prev_posts_count=reel.get("prevPostsCount"),
    )

    await db.upsert_reel_metrics(
        reel_db_id=reel_id,
        views=metrics.views,
        likes=metrics.likes,
        comments_count=metrics.comments_count,
        saves=metrics.saves,
        shares=metrics.shares,
        reach=metrics.reach,
        engagement_rate=metrics.engagement_rate,
        save_rate=metrics.save_rate,
        share_rate=metrics.share_rate,
        comment_rate=metrics.comment_rate,
        virality_score=metrics.virality_score,
        view_to_follower=metrics.view_to_follower,
        metric_quality=metrics.metric_quality,
        is_volatile=metrics.is_volatile,
    )

    await db.insert_reel_snapshot(
        reel_db_id=reel_id,
        views=metrics.views,
        likes=metrics.likes,
        comments_count=metrics.comments_count,
        saves=metrics.saves,
        shares=metrics.shares,
        reach=metrics.reach,
    )

    logger.debug(
        "reel_analytics_computed",
        reel_id=reel_id,
        engagement_rate=metrics.engagement_rate,
        virality_score=metrics.virality_score,
    )

    return metrics


async def run_analytics_pipeline(
    db: DatabaseClient,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    start = time.monotonic()
    reels = await db.get_reels_with_metrics(limit=limit, offset=offset)
    total = len(reels)
    logger.info("analytics_pipeline_started", reel_count=total)

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for reel in reels:
        try:
            metrics = await process_single_reel(reel, db)
            results.append(
                {
                    "reel_id": reel["id"],
                    "engagement_rate": metrics.engagement_rate,
                    "save_rate": metrics.save_rate,
                    "share_rate": metrics.share_rate,
                    "comment_rate": metrics.comment_rate,
                    "virality_score": metrics.virality_score,
                    "view_to_follower": metrics.view_to_follower,
                    "metric_quality": metrics.metric_quality,
                    "is_volatile": metrics.is_volatile,
                }
            )
        except Exception as exc:
            error_msg = f"reel {reel['id']}: {exc}"
            errors.append(error_msg)
            logger.error("analytics_reel_failed", reel_id=reel["id"], error=str(exc))
            db_queries_total.labels(operation="analytics_fail").inc()

    elapsed = time.monotonic() - start
    logger.info(
        "analytics_pipeline_completed",
        processed=len(results),
        failed=len(errors),
        elapsed_sec=round(elapsed, 3),
    )

    return {
        "processed": len(results),
        "failed": len(errors),
        "elapsed_sec": round(elapsed, 3),
        "results": results,
        "errors": errors,
    }


async def snapshot_all_metrics(
    db: DatabaseClient,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    start = time.monotonic()
    reels = await db.get_reels_with_metrics(limit=limit, offset=offset)
    logger.info("snapshot_job_started", reel_count=len(reels))

    inserted = 0
    errors = 0

    for reel in reels:
        try:
            snapshot = await db.insert_reel_snapshot(
                reel_db_id=reel["id"],
                views=reel.get("views", 0) or 0,
                likes=reel.get("likes", 0) or 0,
                comments_count=reel.get("commentsCount", 0) or 0,
                saves=reel.get("saves"),
                shares=reel.get("shares"),
                reach=reel.get("reach"),
            )
            if snapshot:
                inserted += 1
        except Exception as exc:
            errors += 1
            logger.error("snapshot_failed", reel_id=reel["id"], error=str(exc))

    elapsed = time.monotonic() - start
    logger.info(
        "snapshot_job_completed",
        inserted=inserted,
        failed=errors,
        elapsed_sec=round(elapsed, 3),
    )

    return {
        "snapshots_created": inserted,
        "failed": errors,
        "elapsed_sec": round(elapsed, 3),
    }


def compute_metric_decay(
    snapshots: list[dict[str, Any]],
    posted_at: datetime | None = None,
    early_hours: int = EARLY_LIFECYCLE_HOURS,
    late_days: int = LATE_LIFECYCLE_DAYS,
) -> dict[str, Any]:
    if not snapshots:
        return {
            "decay_analysis_possible": False,
            "early_snapshots": 0,
            "late_snapshots": 0,
        }

    def _to_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    if posted_at:
        base = _to_utc(posted_at)
        early_cutoff = base + timedelta(hours=early_hours)
        late_cutoff = base + timedelta(days=late_days)
    else:
        snapshot_times = [
            _to_utc(s.get("snapshotAt"))
            for s in snapshots
            if s.get("snapshotAt")
        ]
        if not snapshot_times:
            return {
                "decay_analysis_possible": False,
                "early_snapshots": 0,
                "late_snapshots": 0,
            }
        earliest = min(snapshot_times)
        early_cutoff = earliest + timedelta(hours=early_hours)
        late_cutoff = earliest + timedelta(days=late_days)

    early: list[dict[str, Any]] = []
    late: list[dict[str, Any]] = []

    for s in snapshots:
        st = _to_utc(s.get("snapshotAt"))
        if st is None:
            continue
        if st <= early_cutoff:
            early.append(s)
        elif st >= late_cutoff:
            late.append(s)

    def avg_engagement(snaps: list[dict[str, Any]]) -> float | None:
        values = [
            (s.get("likes", 0) or 0)
            + (s.get("commentsCount", 0) or 0)
            + (s.get("saves", 0) or 0)
            + (s.get("shares", 0) or 0)
            for s in snaps
            if (s.get("views", 0) or 0) > 0
        ]
        if not values:
            return None
        return round(sum(values) / len(values), 4)

    early_avg = avg_engagement(early)
    late_avg = avg_engagement(late)

    decay_pct = None
    if early_avg is not None and late_avg is not None and early_avg > 0:
        decay_pct = round(((late_avg - early_avg) / early_avg) * 100, 2)

    return {
        "decay_analysis_possible": True,
        "early_snapshots": len(early),
        "late_snapshots": len(late),
        "early_avg_engagement": early_avg,
        "late_avg_engagement": late_avg,
        "decay_percentage": decay_pct,
    }


def format_metrics_output(metrics: ReelMetricsResult) -> str:
    output: dict[str, Any] = {
        "reel_id": metrics.reel_id,
        "engagement_rate": metrics.engagement_rate,
        "virality_score": metrics.virality_score,
        "save_rate": metrics.save_rate,
        "share_rate": metrics.share_rate,
        "comment_rate": metrics.comment_rate,
        "view_to_follower": metrics.view_to_follower,
        "metric_quality": metrics.metric_quality,
        "is_volatile": metrics.is_volatile,
    }
    return json.dumps(output, indent=2)