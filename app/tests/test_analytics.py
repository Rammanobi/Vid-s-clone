from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.analytics import (
    compute_metric_decay,
    format_metrics_output,
    process_single_reel,
    run_analytics_pipeline,
    snapshot_all_metrics,
)
from app.metrics import ReelMetricsResult, compute_reel_metrics


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.upsert_reel_metrics = AsyncMock()
    db.insert_reel_snapshot = AsyncMock(
        return_value={"id": "snap1", "reelId": "r1", "snapshotAt": datetime.now(timezone.utc)}
    )
    return db


class TestProcessSingleReel:
    @pytest.mark.asyncio
    async def test_processes_reel_and_upserts(self, mock_db: AsyncMock) -> None:
        reel = {
            "id": "r1",
            "views": 10000,
            "likes": 800,
            "commentsCount": 50,
            "saves": 100,
            "shares": 50,
            "reach": 15000,
            "followerCount": 5000,
            "durationSec": 60.0,
            "postsCount": 20,
        }
        result = await process_single_reel(reel, mock_db)

        assert isinstance(result, ReelMetricsResult)
        assert result.engagement_rate == 10.0
        assert result.save_rate == 1.0
        assert result.share_rate == 0.5

        mock_db.upsert_reel_metrics.assert_awaited_once()
        call_kwargs = mock_db.upsert_reel_metrics.call_args[1]
        assert call_kwargs["reel_db_id"] == "r1"
        assert call_kwargs["engagement_rate"] == 10.0

        mock_db.insert_reel_snapshot.assert_awaited_once()
        snap_kwargs = mock_db.insert_reel_snapshot.call_args[1]
        assert snap_kwargs["reel_db_id"] == "r1"
        assert snap_kwargs["views"] == 10000

    @pytest.mark.asyncio
    async def test_missing_optionals_handled(self, mock_db: AsyncMock) -> None:
        reel = {
            "id": "r2",
            "views": 5000,
            "likes": 200,
            "commentsCount": 10,
        }
        result = await process_single_reel(reel, mock_db)

        assert result.saves is None
        assert result.shares is None
        assert result.metric_quality == "PARTIAL"

    @pytest.mark.asyncio
    async def test_zero_views(self, mock_db: AsyncMock) -> None:
        reel = {
            "id": "r3",
            "views": 0,
            "likes": 0,
            "commentsCount": 0,
        }
        result = await process_single_reel(reel, mock_db)
        assert result.engagement_rate == 0.0
        # virality_score = engagement_rate * 0.5 + (share_rate or 0.0) * 0.3
        #                  + view_to_follower * 0.2
        # views=0 zero-guards engagement_rate to 0.0, shares is absent so
        # share_rate is None (treated as 0.0), and followerCount is absent
        # so view_to_follower is 0.0 too:
        #   0.0 * 0.5 + 0.0 * 0.3 + 0.0 * 0.2 = 0.0
        # A reel nobody watched has no virality - the old formula's
        # arbitrary +1.0 floor is gone.
        assert result.virality_score == 0.0

    @pytest.mark.asyncio
    async def test_low_follower_volatility(self, mock_db: AsyncMock) -> None:
        reel = {
            "id": "r4",
            "views": 1000,
            "likes": 50,
            "commentsCount": 5,
            "followerCount": 50,
        }
        result = await process_single_reel(reel, mock_db)
        assert result.is_volatile is True
        assert result.view_to_follower == 20.0


class TestRunAnalyticsPipeline:
    @pytest.mark.asyncio
    async def test_processes_batch_of_reels(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {
                    "id": "r1",
                    "views": 10000,
                    "likes": 800,
                    "commentsCount": 50,
                    "saves": 100,
                    "shares": 50,
                    "followerCount": 5000,
                },
                {
                    "id": "r2",
                    "views": 5000,
                    "likes": 200,
                    "commentsCount": 10,
                    "saves": 25,
                    "shares": 5,
                    "followerCount": 2000,
                },
            ]
        )
        result = await run_analytics_pipeline(mock_db, limit=10)

        assert result["processed"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2
        assert result["results"][0]["reel_id"] == "r1"
        assert result["results"][0]["engagement_rate"] == 10.0
        assert mock_db.upsert_reel_metrics.await_count == 2
        assert mock_db.insert_reel_snapshot.await_count == 2

    @pytest.mark.asyncio
    async def test_handles_reel_errors_gracefully(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"id": "r1", "views": 1000, "likes": 50, "commentsCount": 5},
                {"id": "r2", "views": 2000, "likes": 100, "commentsCount": 10},
            ]
        )
        mock_db.upsert_reel_metrics = AsyncMock(side_effect=[None, ValueError("DB error")])

        result = await run_analytics_pipeline(mock_db, limit=10)

        assert result["processed"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert "DB error" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_empty_batch(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(return_value=[])
        result = await run_analytics_pipeline(mock_db)
        assert result["processed"] == 0
        assert result["failed"] == 0
        assert result["elapsed_sec"] >= 0

    @pytest.mark.asyncio
    async def test_elapsed_time_tracked(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[{"id": "r1", "views": 100, "likes": 5, "commentsCount": 1}]
        )
        result = await run_analytics_pipeline(mock_db)
        # elapsed_sec is a real time.monotonic() delta. Processing a single
        # mocked reel can finish in under a millisecond and round to 0.0 on
        # a fast machine, so assert the field exists and is a non-negative
        # float rather than strictly positive (asserting > 0 here is flaky,
        # not a real invariant of the pipeline).
        assert "elapsed_sec" in result
        assert isinstance(result["elapsed_sec"], float)
        assert result["elapsed_sec"] >= 0


class TestSnapshotAllMetrics:
    @pytest.mark.asyncio
    async def test_snapshots_all_reels(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"id": "r1", "views": 1000, "likes": 50, "commentsCount": 5},
                {"id": "r2", "views": 2000, "likes": 100, "commentsCount": 10, "saves": 20, "shares": 5},
            ]
        )
        mock_db.insert_reel_snapshot = AsyncMock(
            side_effect=[
                {"id": "s1", "reelId": "r1", "snapshotAt": datetime.now(timezone.utc)},
                {"id": "s2", "reelId": "r2", "snapshotAt": datetime.now(timezone.utc)},
            ]
        )
        result = await snapshot_all_metrics(mock_db, limit=10)

        assert result["snapshots_created"] == 2
        assert result["failed"] == 0
        assert mock_db.insert_reel_snapshot.await_count == 2

    @pytest.mark.asyncio
    async def test_no_reels(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(return_value=[])
        result = await snapshot_all_metrics(mock_db)
        assert result["snapshots_created"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_snapshot_failure(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"id": "r1", "views": 1000, "likes": 50, "commentsCount": 5},
                {"id": "r2", "views": 2000, "likes": 100, "commentsCount": 10},
            ]
        )
        mock_db.insert_reel_snapshot = AsyncMock(
            side_effect=[{"id": "s1", "reelId": "r1", "snapshotAt": datetime.now(timezone.utc)}, RuntimeError("snap fail")]
        )
        result = await snapshot_all_metrics(mock_db, limit=10)

        assert result["snapshots_created"] == 1
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_passes_raw_counts_to_snapshot(self, mock_db: AsyncMock) -> None:
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"id": "r1", "views": 5000, "likes": 300, "commentsCount": 15, "saves": 50, "shares": 10, "reach": 8000}
            ]
        )
        await snapshot_all_metrics(mock_db, limit=10)

        call_kwargs = mock_db.insert_reel_snapshot.call_args[1]
        assert call_kwargs["views"] == 5000
        assert call_kwargs["likes"] == 300
        assert call_kwargs["comments_count"] == 15
        assert call_kwargs["saves"] == 50
        assert call_kwargs["shares"] == 10
        # reach was removed from insert_reel_snapshot's signature (see
        # app/db.py::insert_reel_snapshot and
        # openspec/changes/fix-hiker-ingestion/specs/reel-metrics/spec.md,
        # "Reach and impressions are unavailable" - HikerAPI has no
        # reach/impressions field for Reels). Even though the raw reel dict
        # above still carries a stale "reach" key, it must not be forwarded.
        assert "reach" not in call_kwargs


class TestComputeMetricDecay:
    def test_empty_snapshots(self) -> None:
        result = compute_metric_decay([])
        assert result["decay_analysis_possible"] is False
        assert result["early_snapshots"] == 0
        assert result["late_snapshots"] == 0

    def test_no_snapshot_times(self) -> None:
        result = compute_metric_decay([{"id": "s1"}, {"id": "s2"}])
        assert result["decay_analysis_possible"] is False

    def test_positive_decay(self) -> None:
        now = datetime.now(timezone.utc)
        posted_at = now - timedelta(days=10)
        snapshots = [
            {"id": "s1", "snapshotAt": posted_at + timedelta(hours=1), "views": 1000, "likes": 200, "commentsCount": 20, "saves": 50, "shares": 10},
            {"id": "s2", "snapshotAt": posted_at + timedelta(hours=2), "views": 1000, "likes": 180, "commentsCount": 15, "saves": 40, "shares": 8},
            {"id": "s3", "snapshotAt": posted_at + timedelta(days=10), "views": 1000, "likes": 50, "commentsCount": 5, "saves": 10, "shares": 2},
            {"id": "s4", "snapshotAt": posted_at + timedelta(days=11), "views": 1000, "likes": 40, "commentsCount": 3, "saves": 8, "shares": 1},
        ]

        with patch("app.analytics.EARLY_LIFECYCLE_HOURS", 24), \
             patch("app.analytics.LATE_LIFECYCLE_DAYS", 7):
            result = compute_metric_decay(snapshots, posted_at=posted_at)

        assert result["decay_analysis_possible"] is True
        assert result["early_snapshots"] == 2
        assert result["late_snapshots"] == 2
        assert result["decay_percentage"] is not None
        assert result["decay_percentage"] < 0

    def test_no_decay_identical_engagement(self) -> None:
        now = datetime.now(timezone.utc)
        posted_at = now - timedelta(days=10)

        def make_snap(hours_offset: int) -> dict[str, Any]:
            return {
                "id": f"s{hours_offset}",
                "snapshotAt": posted_at + timedelta(hours=hours_offset),
                "views": 1000, "likes": 100, "commentsCount": 10,
                "saves": 20, "shares": 5,
            }

        snapshots = [make_snap(1), make_snap(2), make_snap(200), make_snap(201)]

        with patch("app.analytics.EARLY_LIFECYCLE_HOURS", 24), \
             patch("app.analytics.LATE_LIFECYCLE_DAYS", 7):
            result = compute_metric_decay(snapshots, posted_at=posted_at)

        assert result["decay_percentage"] == 0.0

    def test_no_late_snapshots(self) -> None:
        now = datetime.now(timezone.utc)
        posted_at = now - timedelta(hours=2)
        snapshots = [
            {"id": "s1", "snapshotAt": posted_at + timedelta(minutes=30), "views": 100, "likes": 10, "commentsCount": 1, "saves": 2, "shares": 0},
        ]

        with patch("app.analytics.EARLY_LIFECYCLE_HOURS", 24), \
             patch("app.analytics.LATE_LIFECYCLE_DAYS", 7):
            result = compute_metric_decay(snapshots, posted_at=posted_at)

        assert result["decay_analysis_possible"] is True
        assert result["early_snapshots"] == 1
        assert result["late_snapshots"] == 0
        assert result["late_avg_engagement"] is None

    def test_naive_datetime_conversion(self) -> None:
        now_naive = datetime.now()
        posted = now_naive - timedelta(days=5)
        snapshots = [
            {"id": "s1", "snapshotAt": posted + timedelta(hours=1), "views": 100, "likes": 20, "commentsCount": 2, "saves": 5, "shares": 1},
        ]
        result = compute_metric_decay(snapshots, posted_at=posted)
        assert result["decay_analysis_possible"] is True

    def test_no_posted_at_fallback_to_earliest_snapshot(self) -> None:
        now = datetime.now(timezone.utc)
        snapshots = [
            {"id": "s1", "snapshotAt": now - timedelta(days=10), "views": 100, "likes": 50, "commentsCount": 5, "saves": 10, "shares": 2},
            {"id": "s2", "snapshotAt": now - timedelta(days=9), "views": 100, "likes": 40, "commentsCount": 4, "saves": 8, "shares": 1},
        ]
        result = compute_metric_decay(snapshots)
        assert result["decay_analysis_possible"] is True


class TestFormatMetricsOutput:
    def test_outputs_valid_json(self) -> None:
        metrics = compute_reel_metrics(
            reel_id="r1",
            views=10000,
            likes=800,
            comments_count=50,
            saves=100,
            shares=50,
            follower_count=5000,
            prev_follower_count=4000,
        )
        output = format_metrics_output(metrics)
        parsed = json.loads(output)

        assert parsed["reel_id"] == "r1"
        assert parsed["engagement_rate"] == 10.0
        assert parsed["virality_score"] is not None
        assert parsed["save_rate"] == 1.0
        assert parsed["share_rate"] == 0.5
        assert parsed["view_to_follower"] == 2.0
        assert parsed["metric_quality"] == "FULL"
        assert parsed["is_volatile"] is False

    def test_partial_metrics_in_output(self) -> None:
        metrics = compute_reel_metrics(
            reel_id="r2",
            views=5000,
            likes=200,
            comments_count=10,
        )
        output = format_metrics_output(metrics)
        parsed = json.loads(output)

        assert parsed["save_rate"] is None
        assert parsed["share_rate"] is None
        assert parsed["metric_quality"] == "PARTIAL"

    def test_output_is_indented_json(self) -> None:
        metrics = compute_reel_metrics(reel_id="r3", views=100, likes=5, comments_count=1)
        output = format_metrics_output(metrics)
        assert "\n" in output
        assert output.startswith("{")