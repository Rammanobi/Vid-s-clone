from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hiker_ingestion.mapper import (
    map_account,
    map_comment,
    map_metric,
    map_reel,
)
from hiker_ingestion.models import MetricQuality


class TestMapAccount:
    def test_full_data(self) -> None:
        raw = {
            "pk": "12345",
            "username": "testuser",
            "follower_count": 1000,
            "following_count": 200,
            "media_count": 50,
        }
        result = map_account(raw)
        assert result.instagram_id == "12345"
        assert result.username == "testuser"
        assert result.follower_count == 1000
        assert result.following_count == 200
        assert result.posts_count == 50
        assert result.is_competitor is False

    def test_minimal_data(self) -> None:
        raw = {"username": "minimal"}
        result = map_account(raw)
        assert result.instagram_id == ""
        assert result.username == "minimal"
        assert result.follower_count == 0
        assert result.following_count == 0
        assert result.posts_count == 0

    def test_null_counts(self) -> None:
        raw = {
            "pk": "1",
            "username": "u",
            "follower_count": None,
            "following_count": None,
        }
        result = map_account(raw)
        assert result.follower_count == 0
        assert result.following_count == 0

    def test_alternate_field_names(self) -> None:
        raw = {
            "id": "999",
            "username": "alt",
            "followerCount": 500,
            "postsCount": 10,
        }
        result = map_account(raw)
        assert result.instagram_id == "999"
        assert result.follower_count == 500
        assert result.posts_count == 10


class TestMapReel:
    def test_full_data(self) -> None:
        raw = {
            "pk": "reel1",
            "video_url": "https://example.com/video.mp4",
            "caption_text": "Test caption",
            "video_duration": 30.5,
            "taken_at": 1700000000,
        }
        result = map_reel(raw, "account-uuid")
        assert result.account_id == "account-uuid"
        assert result.instagram_reel_id == "reel1"
        assert result.video_url == "https://example.com/video.mp4"
        assert result.caption == "Test caption"
        assert result.duration_sec == 30.5
        assert result.posted_at is not None

    def test_caption_as_object(self) -> None:
        raw = {
            "pk": "r2",
            "video_url": "url",
            "caption": {"text": "nested caption"},
        }
        result = map_reel(raw, "aid")
        assert result.caption == "nested caption"

    def test_minimal_data(self) -> None:
        raw = {"pk": "r3"}
        result = map_reel(raw, "aid")
        assert result.video_url == ""

    def test_empty_caption(self) -> None:
        raw = {"pk": "r4", "video_url": "url", "caption_text": ""}
        result = map_reel(raw, "aid")
        assert result.caption is None


class TestMapComment:
    def test_full_data(self) -> None:
        raw = {
            "pk": "commenter1",
            "text": "Great reel!",
            "created_at": 1700000000,
        }
        result = map_comment(raw, "reel-uuid", "creator1")
        assert result.reel_id == "reel-uuid"
        assert result.author_id == "commenter1"
        assert result.text == "Great reel!"
        assert result.is_creator is False
        assert result.posted_at is not None

    def test_creator_comment(self) -> None:
        raw = {"pk": "creator1", "text": "Thanks!"}
        result = map_comment(raw, "rid", "creator1")
        assert result.is_creator is True

    def test_minimal_data(self) -> None:
        raw: dict = {}
        result = map_comment(raw, "rid")
        assert result.author_id == ""
        assert result.text == ""


class TestMapMetric:
    def test_full_metrics(self) -> None:
        raw = {
            "view_count": 10000,
            "like_count": 500,
            "comment_count": 50,
            "save_count": 200,
            "share_count": 100,
            "reach_count": 15000,
        }
        result = map_metric(raw, "reel-uuid", follower_count=5000)
        assert result.reel_id == "reel-uuid"
        assert result.views == 10000
        assert result.likes == 500
        assert result.comments_count == 50
        assert result.saves == 200
        assert result.shares == 100
        assert result.reach == 15000
        assert result.metric_quality == MetricQuality.FULL

    def test_partial_metrics(self) -> None:
        raw = {
            "view_count": 1000,
            "like_count": 50,
            "comment_count": 5,
        }
        result = map_metric(raw, "rid")
        assert result.saves is None
        assert result.shares is None
        assert result.metric_quality == MetricQuality.PARTIAL

    def test_engagement_rate_calculation(self) -> None:
        raw = {
            "view_count": 1000,
            "like_count": 100,
            "comment_count": 10,
            "save_count": 20,
            "share_count": 5,
        }
        result = map_metric(raw, "rid", follower_count=1000)
        expected_er = ((100 + 10 + 20 + 5) / 1000) * 100
        assert result.engagement_rate == round(expected_er, 4)
        assert result.virality_score > 1.0

    def test_zero_follower_guard(self) -> None:
        raw = {
            "view_count": 100,
            "like_count": 10,
            "comment_count": 1,
        }
        result = map_metric(raw, "rid", follower_count=0)
        assert result.engagement_rate == 0.0
        assert result.view_to_follower == 0.0
        assert result.virality_score == 1.0


class TestMapMetricEdgeCases:
    def test_null_numeric_fields(self) -> None:
        raw = {
            "view_count": None,
            "like_count": None,
            "comment_count": None,
        }
        result = map_metric(raw, "rid")
        assert result.views == 0
        assert result.likes == 0
        assert result.comments_count == 0

    def test_high_virality(self) -> None:
        raw = {
            "view_count": 1000000,
            "like_count": 500000,
            "comment_count": 100000,
            "save_count": 200000,
            "share_count": 150000,
        }
        result = map_metric(raw, "rid", follower_count=10000)
        assert result.virality_score > 2.0
        assert result.view_to_follower > 50.0