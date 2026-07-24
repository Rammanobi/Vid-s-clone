from __future__ import annotations

import pytest

from app.metrics import (
    ReelMetricsResult,
    compute_audience_growth,
    compute_avg_watch_time,
    compute_comment_rate,
    compute_content_consistency,
    compute_engagement_rate,
    compute_growth_rate,
    compute_posting_frequency,
    compute_reel_metrics,
    compute_save_rate,
    compute_share_rate,
    compute_view_to_follower,
    compute_virality_score,
    is_follower_count_volatile,
)


class TestEngagementRate:
    def test_basic_engagement(self) -> None:
        rate, quality = compute_engagement_rate(
            likes=80, comments=10, saves=5, shares=5, views=1000
        )
        assert rate == 10.0
        assert quality == "FULL"

    def test_zero_views_returns_zero(self) -> None:
        rate, quality = compute_engagement_rate(
            likes=50, comments=5, saves=2, shares=1, views=0
        )
        assert rate == 0.0

    def test_partial_quality_when_saves_missing(self) -> None:
        rate, quality = compute_engagement_rate(
            likes=80, comments=10, saves=None, shares=5, views=1000
        )
        assert rate == 9.5
        assert quality == "PARTIAL"

    def test_partial_quality_when_shares_missing(self) -> None:
        rate, quality = compute_engagement_rate(
            likes=80, comments=10, saves=5, shares=None, views=1000
        )
        assert rate == 9.5
        assert quality == "PARTIAL"

    def test_partial_when_both_missing(self) -> None:
        rate, quality = compute_engagement_rate(
            likes=80, comments=10, saves=None, shares=None, views=1000
        )
        assert rate == 9.0
        assert quality == "PARTIAL"

    def test_no_engagement(self) -> None:
        rate, quality = compute_engagement_rate(
            likes=0, comments=0, saves=0, shares=0, views=1000
        )
        assert rate == 0.0
        assert quality == "FULL"


class TestSaveRate:
    def test_basic(self) -> None:
        rate, quality = compute_save_rate(saves=50, views=1000)
        assert rate == 5.0
        assert quality == "FULL"

    def test_none_saves_returns_none_partial(self) -> None:
        rate, quality = compute_save_rate(saves=None, views=1000)
        assert rate is None
        assert quality == "PARTIAL"

    def test_zero_views(self) -> None:
        rate, quality = compute_save_rate(saves=50, views=0)
        assert rate == 0.0

    def test_no_saves(self) -> None:
        rate, quality = compute_save_rate(saves=0, views=1000)
        assert rate == 0.0


class TestShareRate:
    def test_basic(self) -> None:
        rate, quality = compute_share_rate(shares=30, views=1000)
        assert rate == 3.0
        assert quality == "FULL"

    def test_none_shares_returns_none_partial(self) -> None:
        rate, quality = compute_share_rate(shares=None, views=1000)
        assert rate is None
        assert quality == "PARTIAL"

    def test_zero_views(self) -> None:
        rate, quality = compute_share_rate(shares=30, views=0)
        assert rate == 0.0


class TestCommentRate:
    def test_basic(self) -> None:
        rate, quality = compute_comment_rate(comments=20, views=1000)
        assert rate == 2.0
        assert quality == "FULL"

    def test_zero_views(self) -> None:
        rate, quality = compute_comment_rate(comments=20, views=0)
        assert rate == 0.0

    def test_comments_disabled(self) -> None:
        rate, quality = compute_comment_rate(
            comments=50, views=1000, comments_disabled=True
        )
        assert rate == 0.0

    def test_no_comments(self) -> None:
        rate, quality = compute_comment_rate(comments=0, views=1000)
        assert rate == 0.0


class TestViralityScore:
    def test_basic(self) -> None:
        score = compute_virality_score(
            likes=500, comments=50, saves=30, shares=20, views=10000
        )
        ratios = [500 / 10000, 50 / 10000, 30 / 10000, 20 / 10000]
        expected = round(sum(sorted(ratios)[1:-1]) / 2.0, 6)
        assert score == expected

    def test_zero_views(self) -> None:
        score = compute_virality_score(
            likes=500, comments=50, saves=30, shares=20, views=0
        )
        assert score == 1.0

    def test_missing_saves(self) -> None:
        score = compute_virality_score(
            likes=500, comments=50, saves=None, shares=20, views=10000
        )
        ratios = [500 / 10000, 50 / 10000, 20 / 10000]
        expected = round(sorted(ratios)[len(ratios) // 2], 6)
        assert score == expected

    def test_no_engagement(self) -> None:
        score = compute_virality_score(
            likes=0, comments=0, saves=0, shares=0, views=10000
        )
        assert score == 0.0

    def test_median_not_mean(self) -> None:
        score = compute_virality_score(
            likes=9000, comments=10, saves=8, shares=6, views=10000
        )
        ratios = [0.9, 0.001, 0.0008, 0.0006]
        sorted_r = sorted(ratios)
        n = len(sorted_r)
        median = (sorted_r[n // 2 - 1] + sorted_r[n // 2]) / 2.0
        mean = sum(ratios) / len(ratios)
        assert score == round(median, 6)
        assert score != round(mean, 6)


class TestViewToFollower:
    def test_basic(self) -> None:
        ratio = compute_view_to_follower(views=50000, follower_count=10000)
        assert ratio == 5.0

    def test_zero_followers(self) -> None:
        ratio = compute_view_to_follower(views=50000, follower_count=0)
        assert ratio == 0.0

    def test_none_followers(self) -> None:
        ratio = compute_view_to_follower(views=50000, follower_count=None)
        assert ratio == 0.0

    def test_less_than_one(self) -> None:
        ratio = compute_view_to_follower(views=100, follower_count=1000)
        assert ratio == 0.1


class TestGrowthRate:
    def test_positive_growth(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=1500, prev_followers=1000
        )
        assert rate == 50.0
        assert quality == "FULL"

    def test_negative_growth(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=800, prev_followers=1000
        )
        assert rate == -20.0
        assert quality == "FULL"

    def test_zero_growth(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=1000, prev_followers=1000
        )
        assert rate == 0.0
        assert quality == "FULL"

    def test_zero_starting_followers_fallback_to_absolute(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=500, prev_followers=0
        )
        assert rate == 500.0
        assert quality == "PARTIAL"

    def test_both_zero(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=0, prev_followers=0
        )
        assert rate == 0.0

    def test_none_values(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=None, prev_followers=1000
        )
        assert rate is None
        assert quality == "PARTIAL"

    def test_negative_followers_not_possible(self) -> None:
        rate, quality = compute_growth_rate(
            current_followers=0, prev_followers=1000
        )
        assert rate == -100.0
        assert quality == "FULL"


class TestPostingFrequency:
    def test_basic(self) -> None:
        freq = compute_posting_frequency(
            posts_count=15, prev_posts_count=5, time_period_days=14
        )
        assert freq == 5.0

    def test_none_values(self) -> None:
        freq = compute_posting_frequency(
            posts_count=None, prev_posts_count=5
        )
        assert freq is None

    def test_no_new_posts(self) -> None:
        freq = compute_posting_frequency(
            posts_count=10, prev_posts_count=10, time_period_days=30
        )
        assert freq == 0.0

    def test_negative_diff_clamped(self) -> None:
        freq = compute_posting_frequency(
            posts_count=5, prev_posts_count=10, time_period_days=7
        )
        assert freq == 0.0

    def test_default_period(self) -> None:
        freq = compute_posting_frequency(
            posts_count=8, prev_posts_count=4, time_period_days=30
        )
        weeks = 30 / 7.0
        assert freq == round(4 / weeks, 4)


class TestAvgWatchTime:
    def test_with_total_watch_time(self) -> None:
        avg = compute_avg_watch_time(
            duration_sec=60.0, views=100, total_watch_time_sec=3000.0
        )
        assert avg == 30.0

    def test_fallback_to_duration_half(self) -> None:
        avg = compute_avg_watch_time(
            duration_sec=60.0, views=100, total_watch_time_sec=None
        )
        assert avg == 30.0

    def test_no_data(self) -> None:
        avg = compute_avg_watch_time(
            duration_sec=None, views=0, total_watch_time_sec=None
        )
        assert avg is None

    def test_zero_views_with_watch_time(self) -> None:
        avg = compute_avg_watch_time(
            duration_sec=60.0, views=0, total_watch_time_sec=100.0
        )
        assert avg == 30.0


class TestContentConsistency:
    def test_exact_match(self) -> None:
        consistency = compute_content_consistency(
            current_topic="cooking",
            previous_topics=["cooking", "cooking", "travel"],
        )
        assert consistency == 0.6667

    def test_no_previous_topics(self) -> None:
        consistency = compute_content_consistency(
            current_topic="cooking", previous_topics=None
        )
        assert consistency is None

    def test_empty_previous_list(self) -> None:
        consistency = compute_content_consistency(
            current_topic="cooking", previous_topics=[]
        )
        assert consistency == 0.0

    def test_no_match(self) -> None:
        consistency = compute_content_consistency(
            current_topic="cooking",
            previous_topics=["travel", "fitness", "music"],
        )
        assert consistency == 0.0

    def test_none_current_topic(self) -> None:
        consistency = compute_content_consistency(
            current_topic=None, previous_topics=["cooking"]
        )
        assert consistency is None


class TestAudienceGrowth:
    def test_positive_growth(self) -> None:
        growth = compute_audience_growth(
            current_followers=1500, prev_followers=1000
        )
        assert growth == 500

    def test_negative_growth(self) -> None:
        growth = compute_audience_growth(
            current_followers=800, prev_followers=1000
        )
        assert growth == -200

    def test_none_values(self) -> None:
        growth = compute_audience_growth(
            current_followers=None, prev_followers=1000
        )
        assert growth is None


class TestIsVolatile:
    def test_below_threshold(self) -> None:
        assert is_follower_count_volatile(50) is True

    def test_at_threshold(self) -> None:
        assert is_follower_count_volatile(100) is False

    def test_above_threshold(self) -> None:
        assert is_follower_count_volatile(10000) is False

    def test_none_is_volatile(self) -> None:
        assert is_follower_count_volatile(None) is True


class TestComputeReelMetrics:
    def test_full_metrics(self) -> None:
        result = compute_reel_metrics(
            reel_id="r1",
            views=10000,
            likes=800,
            comments_count=50,
            saves=100,
            shares=50,
            reach=15000,
            follower_count=5000,
            prev_follower_count=4000,
            duration_sec=60.0,
            posts_count=20,
            prev_posts_count=10,
            time_period_days=30,
        )
        assert result.engagement_rate == 10.0
        assert result.save_rate == 1.0
        assert result.share_rate == 0.5
        assert result.comment_rate == 0.5
        assert result.view_to_follower == 2.0
        assert result.metric_quality == "FULL"
        assert result.is_volatile is False
        assert result.growth_rate is not None
        assert result.posting_frequency is not None

    def test_zero_views(self) -> None:
        result = compute_reel_metrics(
            reel_id="r2", views=0, likes=100, comments_count=10
        )
        assert result.engagement_rate == 0.0
        assert result.comment_rate == 0.0
        assert result.virality_score == 1.0

    def test_missing_saves_shares(self) -> None:
        result = compute_reel_metrics(
            reel_id="r3",
            views=10000,
            likes=800,
            comments_count=50,
            saves=None,
            shares=None,
        )
        assert result.save_rate is None
        assert result.share_rate is None
        assert result.metric_quality == "PARTIAL"

    def test_low_follower_volatility(self) -> None:
        result = compute_reel_metrics(
            reel_id="r4",
            views=1000,
            likes=100,
            comments_count=10,
            saves=5,
            shares=2,
            follower_count=50,
        )
        assert result.is_volatile is True
        assert result.view_to_follower == 20.0

    def test_no_follower_data(self) -> None:
        result = compute_reel_metrics(
            reel_id="r5",
            views=1000,
            likes=100,
            comments_count=10,
            follower_count=None,
        )
        assert result.view_to_follower == 0.0

    def test_comments_disabled(self) -> None:
        result = compute_reel_metrics(
            reel_id="r6",
            views=1000,
            likes=100,
            comments_count=50,
            comments_disabled=True,
        )
        assert result.comment_rate == 0.0

    def test_zero_starting_followers_growth(self) -> None:
        result = compute_reel_metrics(
            reel_id="r7",
            views=1000,
            likes=100,
            comments_count=10,
            follower_count=500,
            prev_follower_count=0,
        )
        assert result.growth_rate == 500.0

    def test_result_is_dataclass(self) -> None:
        result = compute_reel_metrics(reel_id="r8")
        assert isinstance(result, ReelMetricsResult)
        assert result.reel_id == "r8"

    def test_partial_quality_propagates_correctly(self) -> None:
        result = compute_reel_metrics(
            reel_id="r9",
            views=10000,
            likes=800,
            comments_count=50,
            saves=None,
            shares=30,
            follower_count=None,
            prev_follower_count=None,
        )
        assert result.metric_quality == "PARTIAL"


class TestComputeReelMetricsEdgeCases:
    def test_zero_denominators_all(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge1",
            views=0,
            likes=0,
            comments_count=0,
            saves=0,
            shares=0,
            follower_count=0,
        )
        assert result.engagement_rate == 0.0
        assert result.save_rate == 0.0
        assert result.share_rate == 0.0
        assert result.comment_rate == 0.0
        assert result.virality_score == 1.0
        assert result.view_to_follower == 0.0

    def test_missing_all_optionals(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge2",
            views=500,
            likes=25,
            comments_count=2,
        )
        assert result.saves is None
        assert result.shares is None
        assert result.reach is None
        assert result.save_rate is None
        assert result.share_rate is None
        assert result.metric_quality == "PARTIAL"

    def test_large_numbers(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge3",
            views=10_000_000,
            likes=500_000,
            comments_count=25_000,
            saves=100_000,
            shares=75_000,
            follower_count=1_000_000,
        )
        assert result.engagement_rate == 7.0
        assert result.view_to_follower == 10.0
        assert result.is_volatile is False

    def test_high_engagement_rate(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge4",
            views=100,
            likes=50,
            comments_count=10,
            saves=20,
            shares=20,
        )
        assert result.engagement_rate == 100.0

    def test_virality_score_with_all_zeros(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge5",
            views=1000,
            likes=0,
            comments_count=0,
            saves=0,
            shares=0,
        )
        assert result.virality_score == 0.0

    def test_content_consistency_integration(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge6",
            views=1000,
            likes=50,
            comments_count=5,
            current_topic="fitness",
            previous_topics=["fitness", "cooking", "fitness"],
        )
        assert result.content_consistency == 0.6667

    def test_audience_growth_integration(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge7",
            views=1000,
            likes=50,
            comments_count=5,
            follower_count=2000,
            prev_follower_count=1500,
        )
        assert result.audience_growth == 500

    def test_none_follower_count_is_volatile(self) -> None:
        result = compute_reel_metrics(
            reel_id="edge8", views=100, likes=5, comments_count=1
        )
        assert result.follower_count is None
        assert result.is_volatile is True