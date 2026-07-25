from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.competitor_integration import (
    fetch_competitor_strategies,
    fetch_trending_data,
    merge_competitor_trends,
)
from app.creator_pipeline import (
    build_creator_intelligence,
    format_creator_profile_output,
    persist_creator_profile,
    run_creator_intelligence_pipeline,
)
from app.main import app
from app.patterns import (
    analyze_patterns,
    detect_content_gaps,
    detect_seasonal_trends,
    find_audience_interests,
    find_best_content_formats,
    find_best_duration_range,
    find_best_hook_types,
    find_best_posting_day,
    find_best_topics,
    find_worst_topics,
)

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


def _make_reel(
    idx: int,
    topic: str | None = None,
    hook_type: str | None = None,
    content_format: str | None = None,
    duration_sec: float | None = None,
    posted_at: datetime | None = None,
    engagement_rate: float = 5.0,
    virality_score: float = 1.0,
    audience_intent: str | None = None,
    sentiment: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"r{idx}",
        "topic": topic,
        "hookType": hook_type,
        "hook_type": hook_type,
        "contentFormat": content_format,
        "content_format": content_format,
        "durationSec": duration_sec,
        "duration_sec": duration_sec,
        "postedAt": posted_at or NOW,
        "engagementRate": engagement_rate,
        "engagement_rate": engagement_rate,
        "viralityScore": virality_score,
        "virality_score": virality_score,
        "audienceIntent": audience_intent,
        "audience_intent": audience_intent,
        "sentiment": sentiment,
    }


class TestFindBestTopics:
    def test_single_topic(self) -> None:
        reels = [
            _make_reel(1, topic="AI", engagement_rate=10.0),
            _make_reel(2, topic="AI", engagement_rate=8.0),
        ]
        assert find_best_topics(reels) == ["AI"]

    def test_multiple_topics_ranked(self) -> None:
        reels = [
            _make_reel(1, topic="AI", engagement_rate=10.0),
            _make_reel(2, topic="AI", engagement_rate=8.0),
            _make_reel(3, topic="Automation", engagement_rate=5.0),
            _make_reel(4, topic="Productivity", engagement_rate=2.0),
        ]
        result = find_best_topics(reels, top_n=2)
        assert result == ["AI", "Automation"]

    def test_no_topics_returns_empty(self) -> None:
        reels = [_make_reel(1, topic=None)]
        assert find_best_topics(reels) == []

    def test_empty_reels(self) -> None:
        assert find_best_topics([]) == []

    def test_top_n_respected(self) -> None:
        reels = [
            _make_reel(1, topic="A", engagement_rate=10.0),
            _make_reel(2, topic="B", engagement_rate=8.0),
            _make_reel(3, topic="C", engagement_rate=6.0),
        ]
        assert len(find_best_topics(reels, top_n=2)) == 2


class TestFindWorstTopics:
    def test_lowest_engagement_is_worst(self) -> None:
        reels = [
            _make_reel(1, topic="AI", engagement_rate=10.0),
            _make_reel(2, topic="AI", engagement_rate=8.0),
            _make_reel(3, topic="Automation", engagement_rate=2.0),
            _make_reel(4, topic="Productivity", engagement_rate=5.0),
        ]
        result = find_worst_topics(reels, top_n=2)
        assert result == ["Automation", "Productivity"]

    def test_empty_reels(self) -> None:
        assert find_worst_topics([]) == []


class TestFindBestHookTypes:
    def test_ranks_by_avg_engagement(self) -> None:
        reels = [
            _make_reel(1, hook_type="CURIOSITY", engagement_rate=10.0),
            _make_reel(2, hook_type="CURIOSITY", engagement_rate=12.0),
            _make_reel(3, hook_type="STORY", engagement_rate=5.0),
            _make_reel(4, hook_type="QUESTION", engagement_rate=3.0),
        ]
        result = find_best_hook_types(reels, top_n=2)
        assert result[0] == "CURIOSITY"
        assert len(result) == 2

    def test_no_hooks_returns_empty(self) -> None:
        assert find_best_hook_types([_make_reel(1)], top_n=2) == []


class TestFindBestContentFormats:
    def test_ranks_by_avg_engagement(self) -> None:
        reels = [
            _make_reel(1, content_format="TUTORIAL", engagement_rate=9.0),
            _make_reel(2, content_format="TUTORIAL", engagement_rate=11.0),
            _make_reel(3, content_format="SKIT", engagement_rate=4.0),
        ]
        result = find_best_content_formats(reels, top_n=2)
        assert result[0] == "TUTORIAL"

    def test_no_formats_returns_empty(self) -> None:
        assert find_best_content_formats([_make_reel(1)]) == []


class TestFindBestPostingDay:
    def test_best_day_by_engagement(self) -> None:
        monday = NOW.replace(hour=10)
        tuesday = NOW.replace(hour=10)
        monday -= __import__("datetime").timedelta(days=NOW.weekday())
        tuesday = monday + __import__("datetime").timedelta(days=1)

        reels = [
            _make_reel(1, posted_at=monday, engagement_rate=5.0),
            _make_reel(2, posted_at=tuesday, engagement_rate=15.0),
        ]
        assert find_best_posting_day(reels) == "Tuesday"

    def test_returns_none_for_no_dates(self) -> None:
        assert find_best_posting_day([{"id": "r1"}]) is None

    def test_string_date_parsed(self) -> None:
        reels = [
            _make_reel(1, posted_at=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)),
        ]
        result = find_best_posting_day(reels)
        assert result is not None


class TestFindBestDurationRange:
    def test_best_duration_bucket(self) -> None:
        reels = [
            _make_reel(1, duration_sec=10.0, engagement_rate=3.0),
            _make_reel(2, duration_sec=25.0, engagement_rate=15.0),
            _make_reel(3, duration_sec=35.0, engagement_rate=5.0),
        ]
        assert find_best_duration_range(reels) == "15-30 sec"

    def test_no_durations_returns_none(self) -> None:
        assert find_best_duration_range([_make_reel(1)]) is None


class TestFindAudienceInterests:
    def test_most_frequent_topic(self) -> None:
        reels = [
            _make_reel(1, topic="AI"),
            _make_reel(2, topic="AI"),
            _make_reel(3, topic="Design"),
        ]
        result = find_audience_interests(reels, top_n=2)
        assert result[0] == "AI"

    def test_fallback_to_audience_intent(self) -> None:
        reels = [
            _make_reel(1, topic=None, audience_intent="educational"),
            _make_reel(2, topic=None, audience_intent="entertaining"),
        ]
        result = find_audience_interests(reels)
        assert len(result) == 2

    def test_empty_reels_returns_empty(self) -> None:
        assert find_audience_interests([]) == []


class TestDetectSeasonalTrends:
    def test_best_and_worst_month(self) -> None:
        jan = datetime(2026, 1, 15, tzinfo=timezone.utc)
        jun = datetime(2026, 6, 15, tzinfo=timezone.utc)
        reels = [
            _make_reel(1, posted_at=jan, engagement_rate=2.0),
            _make_reel(2, posted_at=jun, engagement_rate=10.0),
        ]
        result = detect_seasonal_trends(reels)
        assert result["seasonal_trends_possible"] is True
        assert result["best_month"] == 6

    def test_no_dates_returns_false(self) -> None:
        assert detect_seasonal_trends([{}])["seasonal_trends_possible"] is False


class TestDetectContentGaps:
    def test_detects_missing_trending_topics(self) -> None:
        reels = [
            _make_reel(1, topic="AI"),
            _make_reel(2, topic="Automation"),
        ]
        gaps = detect_content_gaps(reels, trending_topics=["AI", "Blockchain", "Design"])
        assert "Blockchain" in gaps
        assert "Design" in gaps
        assert "AI" not in gaps

    def test_no_trending_topics(self) -> None:
        reels = [_make_reel(1, topic="AI", audience_intent="educational")]
        gaps = detect_content_gaps(reels)
        assert "untapped_intent:entertaining" in gaps
        assert "untapped_intent:inspiring" in gaps
        assert "untapped_intent:educational" not in gaps

    def test_detects_missing_intents(self) -> None:
        reels = [
            _make_reel(1, topic="AI", audience_intent="educational"),
        ]
        gaps = detect_content_gaps(reels, trending_topics=[])
        has_gap = any("untapped_intent:" in g for g in gaps)
        assert has_gap is True


class TestAnalyzePatterns:
    def test_not_enough_reels(self) -> None:
        result = analyze_patterns([_make_reel(1)])
        assert result["analysis_possible"] is False

    def test_full_analysis(self) -> None:
        reels = [
            _make_reel(1, topic="AI", hook_type="CURIOSITY", content_format="TUTORIAL",
                       duration_sec=25.0, posted_at=NOW, engagement_rate=10.0),
            _make_reel(2, topic="AI", hook_type="CURIOSITY", content_format="TUTORIAL",
                       duration_sec=30.0, posted_at=NOW, engagement_rate=8.0),
            _make_reel(3, topic="Design", hook_type="STORY", content_format="TALKING_HEAD",
                       duration_sec=60.0, posted_at=NOW, engagement_rate=4.0),
        ]
        result = analyze_patterns(reels)
        assert result["analysis_possible"] is True
        assert "best_topics" in result
        assert "worst_topics" in result
        assert "best_hook_types" in result
        assert "best_content_formats" in result
        assert "best_posting_day" in result
        assert "best_duration_range" in result
        assert "audience_interests" in result
        assert "seasonal_trends" in result
        assert "content_gaps" in result


class TestMergeCompetitorTrends:
    def test_merges_formats_and_topics(self) -> None:
        competitors = [
            {"competitorId": "c1", "niche": "AI", "winningFormat": "TUTORIAL", "topTopics": ["AI", "ML"], "avgVirality": 2.0},
        ]
        trends = [
            {"topic": "AI agents", "hookPattern": "you won't believe", "contentFormat": "TALKING_HEAD", "viralityScore": 3.0},
        ]
        result = merge_competitor_trends(competitors, trends)
        assert "TUTORIAL" in result["emerging_formats"]
        assert "TALKING_HEAD" in result["emerging_formats"]
        assert "AI" in result["trending_topics"]
        assert "AI agents" in result["trending_topics"]
        assert len(result["competitor_strategies"]) == 1

    def test_empty_inputs(self) -> None:
        result = merge_competitor_trends([], [])
        assert result["emerging_formats"] == []
        assert result["trending_topics"] == []
        assert result["competitor_strategies"] == []


class TestFetchCompetitorStrategies:
    async def test_fetches_by_niche(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_competitor_insights_by_niche = AsyncMock(
            return_value=[{"competitorId": "c1", "niche": "AI", "topTopics": ["AI"], "avgVirality": 2.0}]
        )
        result = await fetch_competitor_strategies(mock_db, "AI")
        assert len(result) == 1

    async def test_empty_niche(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        result = await fetch_competitor_strategies(mock_db, "unknown")
        assert result == []


class TestFetchTrendingData:
    async def test_fetches_all_topics(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_trends_by_topic = AsyncMock(
            return_value=[{"topic": "AI", "viralityScore": 3.0}]
        )
        result = await fetch_trending_data(mock_db)
        assert len(result) == 1

    async def test_empty_trends(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_trends_by_topic = AsyncMock(return_value=[])
        result = await fetch_trending_data(mock_db, topic="AI")
        assert result == []


class TestBuildCreatorIntelligence:
    async def test_builds_intelligence(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[
                {
                    "id": "r1",
                    "topic": "AI",
                    "hookType": "CURIOSITY",
                    "contentFormat": "TUTORIAL",
                    "durationSec": 25.0,
                    "postedAt": NOW,
                    "views": 1000, "likes": 100, "commentsCount": 10,
                    "saves": 50, "shares": 20, "reach": 2000,
                    "followerCount": 500, "postsCount": 20,
                    "engagementRate": 10.0, "viralityScore": 2.0,
                    "caption": "test", "transcript": "test",
                },
                {
                    "id": "r2",
                    "topic": "AI",
                    "hookType": "CURIOSITY",
                    "contentFormat": "TUTORIAL",
                    "durationSec": 30.0,
                    "postedAt": NOW,
                    "views": 500, "likes": 50, "commentsCount": 5,
                    "saves": 25, "shares": 10, "reach": 1000,
                    "followerCount": 500, "postsCount": 20,
                    "engagementRate": 8.0, "viralityScore": 1.5,
                    "caption": "test", "transcript": "test",
                },
                {
                    "id": "r3",
                    "topic": "Design",
                    "hookType": "STORY",
                    "contentFormat": "TALKING_HEAD",
                    "durationSec": 60.0,
                    "postedAt": NOW,
                    "views": 100, "likes": 5, "commentsCount": 1,
                    "saves": 2, "shares": 0, "reach": 200,
                    "followerCount": 500, "postsCount": 20,
                    "engagementRate": 4.0, "viralityScore": 0.5,
                    "caption": "test", "transcript": "test",
                },
            ]
        )
        mock_db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        mock_db.get_trends_by_topic = AsyncMock(return_value=[])

        result = await build_creator_intelligence(mock_db, limit=50)
        assert result["patterns"]["analysis_possible"] is True
        assert result["patterns"]["best_topics"][0] == "AI"
        assert result["patterns"]["worst_topics"][0] == "Design"
        assert result["patterns"]["best_hook_types"][0] == "CURIOSITY"
        assert result["patterns"]["best_hook_types"][0] == "CURIOSITY"
        assert "competitor_trends" in result

    async def test_single_reel_not_enough_for_patterns(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[{"id": "r1", "engagementRate": 5.0}]
        )
        mock_db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        mock_db.get_trends_by_topic = AsyncMock(return_value=[])

        result = await build_creator_intelligence(mock_db, limit=10)
        assert result["patterns"]["analysis_possible"] is False


class TestPersistCreatorProfile:
    async def test_persists_full_profile(self) -> None:
        mock_db = AsyncMock()
        mock_db.upsert_creator_profile = AsyncMock(
            return_value={"id": "cp1", "accountId": "default", "bestTopics": ["AI"]}
        )
        intelligence = {
            "patterns": {
                "best_topics": ["AI"],
                "worst_topics": ["Design"],
                "best_hook_types": ["CURIOSITY"],
                "best_posting_day": "Tuesday",
                "best_duration_range": "15-30 sec",
                "best_content_formats": ["TUTORIAL"],
                "audience_interests": ["AI", "Productivity"],
                "reel_count": 10,
            },
            "competitor_trends": {
                "trending_topics": [],
                "emerging_formats": [],
                "competitor_strategies": [],
                "trending_hooks": [],
                "trend_count": 0,
            },
        }
        result = await persist_creator_profile(mock_db, intelligence)
        assert result is not None
        mock_db.upsert_creator_profile.assert_awaited_once()
        call_kwargs = mock_db.upsert_creator_profile.call_args[1]
        assert call_kwargs["best_topics"] == ["AI"]
        assert call_kwargs["worst_topics"] == ["Design"]
        assert call_kwargs["best_hook_types"] == ["CURIOSITY"]
        assert call_kwargs["best_posting_day"] == "Tuesday"
        assert call_kwargs["best_content_format"] == "TUTORIAL"

    async def test_persists_empty_patterns(self) -> None:
        mock_db = AsyncMock()
        mock_db.upsert_creator_profile = AsyncMock(
            return_value={"id": "cp1", "accountId": "default", "bestTopics": []}
        )
        intelligence = {
            "patterns": {},
            "competitor_trends": {
                "trending_topics": [],
                "emerging_formats": [],
                "competitor_strategies": [],
                "trending_hooks": [],
                "trend_count": 0,
            },
        }
        result = await persist_creator_profile(mock_db, intelligence)
        assert result is not None


class TestRunCreatorIntelligencePipeline:
    async def test_pipeline_completes(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_full_intelligence = AsyncMock(
            return_value=[
                {
                    "id": "r1",
                    "topic": "AI",
                    "hookType": "CURIOSITY",
                    "contentFormat": "TUTORIAL",
                    "durationSec": 25.0,
                    "postedAt": NOW,
                    "views": 1000, "likes": 100, "commentsCount": 10,
                    "saves": 50, "shares": 20, "reach": 2000,
                    "followerCount": 500, "postsCount": 20,
                    "engagementRate": 10.0, "viralityScore": 2.0,
                    "caption": "test", "transcript": "test",
                },
                {
                    "id": "r2",
                    "topic": "AI",
                    "hookType": "CURIOSITY",
                    "contentFormat": "TUTORIAL",
                    "durationSec": 30.0,
                    "postedAt": NOW,
                    "views": 500, "likes": 50, "commentsCount": 5,
                    "saves": 25, "shares": 10, "reach": 1000,
                    "followerCount": 500, "postsCount": 20,
                    "engagementRate": 8.0, "viralityScore": 1.5,
                    "caption": "test", "transcript": "test",
                },
                {
                    "id": "r3",
                    "topic": "Design",
                    "hookType": "STORY",
                    "contentFormat": "TALKING_HEAD",
                    "durationSec": 60.0,
                    "postedAt": NOW,
                    "views": 100, "likes": 5, "commentsCount": 1,
                    "saves": 2, "shares": 0, "reach": 200,
                    "followerCount": 500, "postsCount": 20,
                    "engagementRate": 4.0, "viralityScore": 0.5,
                    "caption": "test", "transcript": "test",
                },
            ]
        )
        mock_db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        mock_db.get_trends_by_topic = AsyncMock(return_value=[])
        mock_db.upsert_creator_profile = AsyncMock(
            return_value={"id": "cp1", "accountId": "default", "bestTopics": ["AI"]}
        )

        result = await run_creator_intelligence_pipeline(mock_db, limit=50)
        assert result["status"] == "completed"
        assert result["reels_analyzed"] == 3
        assert result["profile_updated"] is True

    async def test_pipeline_handles_db_error(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_full_intelligence = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        result = await run_creator_intelligence_pipeline(mock_db, limit=10)
        assert result["status"] == "failed"
        assert "error" in result

    async def test_pipeline_empty_reels(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_full_intelligence = AsyncMock(return_value=[])
        mock_db.get_competitor_insights_by_niche = AsyncMock(return_value=[])
        mock_db.get_trends_by_topic = AsyncMock(return_value=[])
        mock_db.upsert_creator_profile = AsyncMock(
            return_value={"id": "cp1", "accountId": "default", "bestTopics": []}
        )

        result = await run_creator_intelligence_pipeline(mock_db, limit=10)
        assert result["status"] == "completed"


class TestFormatCreatorProfileOutput:
    def test_formats_full_profile(self) -> None:
        profile = {
            "accountId": "123",
            "bestTopics": ["AI", "Automation"],
            "worstTopics": ["Design"],
            "bestHookTypes": ["CURIOSITY"],
            "bestPostingDay": "Tuesday",
            "bestDurationRange": "20-35 sec",
            "bestContentFormat": "TUTORIAL",
            "audienceInterests": ["Productivity", "AI Tools"],
        }
        output = format_creator_profile_output(profile)
        import json
        parsed = json.loads(output)
        assert parsed["creator_id"] == "123"
        assert parsed["best_topics"] == ["AI", "Automation"]
        assert parsed["best_hook_types"] == ["CURIOSITY"]
        assert parsed["best_posting_day"] == "Tuesday"
        assert parsed["best_duration_range"] == "20-35 sec"
        assert parsed["best_content_format"] == "TUTORIAL"
        assert parsed["audience_interests"] == ["Productivity", "AI Tools"]

    def test_null_profile_returns_error(self) -> None:
        output = format_creator_profile_output(None)
        assert "error" in output


class TestCreatorHealthEndpoint:
    async def test_health_endpoint_returns_status(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/creator/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "database" in data
            assert "reel_count" in data
            assert "profile_exists" in data
            assert "last_run" in data
            assert "version" in data

    async def test_health_endpoint_no_auth_required(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/creator/health")
            assert resp.status_code == 200