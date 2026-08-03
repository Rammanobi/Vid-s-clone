from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.insights import analyze_audience_behavior, analyze_narrative_patterns, analyze_winning_hooks, extract_insights
from app.llm import LLMClient
from app.llm_intelligence import extract_intelligence_hybrid, extract_intelligence_with_llm
from app.main import app

pytestmark = pytest.mark.asyncio


class TestAnalyticsHealthEndpoint:
    async def test_health_endpoint_returns_status(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/analytics/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "database" in data
            assert "reel_count" in data
            assert "last_run" in data
            assert "version" in data

    async def test_health_endpoint_no_auth_required(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/analytics/health")
            assert resp.status_code == 200


class TestLLMClient:
    def _mock_response(self, content: str, status_code: int = 200) -> AsyncMock:
        resp = AsyncMock()
        resp.status_code = status_code
        resp.json = Mock(return_value={"choices": [{"message": {"content": content}}]})
        resp.text = "mock response"
        return resp

    async def test_chat_success(self) -> None:
        client = LLMClient(
            api_key="test-key",
            base_url="http://fake-api.test",
            model="test-model",
            max_retries=1,
            timeout_sec=5,
        )
        mock_resp = self._mock_response('{"topic": "cooking"}')

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.extract_structured(
                system_prompt="analyze", user_prompt="test content"
            )
            assert result == {"topic": "cooking"}

    async def test_chat_retry_on_429(self) -> None:
        client = LLMClient(
            api_key="test-key",
            base_url="http://fake-api.test",
            model="test-model",
            max_retries=2,
            timeout_sec=5,
        )
        resp_429 = self._mock_response("rate limited", status_code=429)
        resp_200 = self._mock_response('{"ok": true}')

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            side_effect=[resp_429, resp_200],
        ):
            result = await client.extract_structured(
                system_prompt="analyze", user_prompt="test"
            )
            assert result == {"ok": True}

    async def test_chat_fails_after_retries(self) -> None:
        client = LLMClient(
            api_key="test-key",
            base_url="http://fake-api.test",
            model="test-model",
            max_retries=2,
            timeout_sec=5,
        )
        resp_500 = self._mock_response("server error", status_code=500)

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            return_value=resp_500,
        ):
            with pytest.raises(Exception, match="LLM API error"):
                await client.extract_structured(
                    system_prompt="analyze", user_prompt="test"
                )

    async def test_chat_timeout_retries(self) -> None:
        client = LLMClient(
            api_key="test-key",
            base_url="http://fake-api.test",
            model="test-model",
            max_retries=1,
            timeout_sec=5,
        )

        async def _timeout(*args: Any, **kwargs: Any) -> AsyncMock:
            raise httpx.TimeoutException("timeout", request=AsyncMock())

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            side_effect=_timeout,
        ):
            with pytest.raises(Exception, match="LLM timeout"):
                await client.extract_structured(
                    system_prompt="analyze", user_prompt="test"
                )

    async def test_extract_structured_parses_json(self) -> None:
        client = LLMClient(
            api_key="test-key",
            base_url="http://fake-api.test",
            model="test-model",
            max_retries=1,
            timeout_sec=5,
        )
        mock_resp = self._mock_response('{"hook_type": "CURIOSITY", "sentiment": "positive"}')

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.extract_structured(
                system_prompt="analyze", user_prompt="test"
            )
            assert result["hook_type"] == "CURIOSITY"
            assert result["sentiment"] == "positive"

    async def test_extract_structured_bad_json_raises(self) -> None:
        client = LLMClient(
            api_key="test-key",
            base_url="http://fake-api.test",
            model="test-model",
            max_retries=1,
            timeout_sec=5,
        )
        mock_resp = self._mock_response("not json")

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(Exception, match="Failed to parse"):
                await client.extract_structured(
                    system_prompt="analyze", user_prompt="test"
                )


class TestLLMIntelligence:
    async def test_llm_extraction_returns_valid_schema(self) -> None:
        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "topic": "cooking pasta",
                "hook_type": "PROBLEM_SOLUTION",
                "hook_text": "here's how to cook perfect pasta",
                "cta": "follow for more recipes",
                "content_format": "TUTORIAL",
                "teaching_style": "step_by_step",
                "narrative_style": "informational",
                "audience_intent": "educational",
                "sentiment": "positive",
                "visual_style": "studio",
            }

        mock_client = AsyncMock()
        mock_client.extract_structured = mock_extract

        result = await extract_intelligence_with_llm(
            reel_db_id="r1",
            transcript="this is how you cook pasta",
            caption="perfect pasta recipe",
            llm_client=mock_client,
        )
        assert result.reel_id == "r1"
        assert result.topic == "cooking pasta"
        assert result.hook_type is not None
        assert result.hook_type.value == "PROBLEM_SOLUTION"
        assert result.content_format is not None
        assert result.content_format.value == "TUTORIAL"
        assert result.sentiment == "positive"

    async def test_llm_extraction_fallback_on_failure(self) -> None:
        mock_client = AsyncMock()
        mock_client.extract_structured = AsyncMock(
            side_effect=Exception("LLM down")
        )

        result = await extract_intelligence_with_llm(
            reel_db_id="r1",
            transcript="some content",
            llm_client=mock_client,
        )
        assert result.reel_id == "r1"
        assert result.topic is None
        assert result.hook_type is None

    async def test_hybrid_uses_llm_when_available(self) -> None:
        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "topic": "llm topic",
                "hook_type": "CURIOSITY",
            }

        mock_client = AsyncMock()
        mock_client.extract_structured = mock_extract

        result = await extract_intelligence_hybrid(
            reel_db_id="r1",
            transcript="amazing content you won't believe",
            caption="check this out",
            llm_client=mock_client,
            use_llm=True,
        )
        assert result.topic == "llm topic"

    async def test_hybrid_falls_back_to_rules_on_llm_failure(self) -> None:
        mock_client = AsyncMock()
        mock_client.extract_structured = AsyncMock(
            side_effect=Exception("LLM down")
        )

        result = await extract_intelligence_hybrid(
            reel_db_id="r1",
            transcript="amazing content you won't believe",
            caption="check this out",
            llm_client=mock_client,
            use_llm=True,
        )
        assert result.reel_id == "r1"
        assert result.topic is not None

    async def test_hybrid_skip_llm_returns_rules_only(self) -> None:
        mock_client = AsyncMock()

        result = await extract_intelligence_hybrid(
            reel_db_id="r1",
            transcript="amazing you won't believe this",
            llm_client=mock_client,
            use_llm=False,
        )
        assert result.hook_type is not None
        mock_client.extract_structured.assert_not_called()


class TestWinningHooks:
    def test_analyze_winning_hooks_basic(self) -> None:
        reels = [
            {
                "intelligence": {"hook_type": "CURIOSITY", "content_format": "TUTORIAL"},
                "metrics": {"engagement_rate": 10.0},
            },
            {
                "intelligence": {"hook_type": "QUESTION", "content_format": "TALKING_HEAD"},
                "metrics": {"engagement_rate": 8.0},
            },
            {
                "intelligence": {"hook_type": "CURIOSITY", "content_format": "TUTORIAL"},
                "metrics": {"engagement_rate": 12.0},
            },
        ]
        result = analyze_winning_hooks(reels, min_reels=2)
        assert result["analysis_possible"] is True
        assert result["winning_hooks"][0]["hook_type"] == "CURIOSITY"
        assert result["winning_hooks"][0]["avg_engagement"] == 11.0

    def test_not_enough_reels(self) -> None:
        result = analyze_winning_hooks([], min_reels=3)
        assert result["analysis_possible"] is False

    def test_analyze_winning_formats(self) -> None:
        reels = [
            {"intelligence": {"hook_type": "STORY", "content_format": "TUTORIAL"}, "metrics": {"engagement_rate": 5.0}},
            {"intelligence": {"hook_type": "STORY", "content_format": "SKIT"}, "metrics": {"engagement_rate": 15.0}},
        ]
        result = analyze_winning_hooks(reels, min_reels=1)
        assert result["winning_formats"][0]["content_format"] == "SKIT"

    def test_empty_intelligence_handled(self) -> None:
        reels = [{"no_intel": True}, {"no_intel": True}]
        result = analyze_winning_hooks(reels, min_reels=1)
        assert result["winning_hooks"] == []


class TestNarrativePatterns:
    def test_basic_distribution(self) -> None:
        reels = [
            {"intelligence": {"narrative_style": "storytelling", "teaching_style": "step_by_step", "sentiment": "positive"}},
            {"intelligence": {"narrative_style": "storytelling", "teaching_style": "demonstration", "sentiment": "positive"}},
            {"intelligence": {"narrative_style": "informational", "teaching_style": "step_by_step", "sentiment": "neutral"}},
        ]
        result = analyze_narrative_patterns(reels)
        assert result["dominant_narrative"] == "storytelling"
        assert result["dominant_teaching_style"] == "step_by_step"
        assert result["narrative_style_distribution"]["storytelling"] == 2
        assert result["sentiment_distribution"]["positive"] == 2

    def test_empty_reels(self) -> None:
        result = analyze_narrative_patterns([])
        assert result["dominant_narrative"] is None

    def test_missing_intelligence(self) -> None:
        result = analyze_narrative_patterns([{}, {"intelligence": {}}])
        assert result["dominant_narrative"] is None


class TestAudienceBehavior:
    def test_basic_metrics(self) -> None:
        reels = [
            {"views": 1000, "likes": 100, "commentsCount": 10, "saves": 50, "shares": 20},
            {"views": 2000, "likes": 200, "commentsCount": 20, "saves": 100, "shares": 40},
        ]
        result = analyze_audience_behavior(reels)
        assert result["total_views"] == 3000
        assert result["total_likes"] == 300
        assert result["avg_views_per_reel"] == 1500.0
        assert result["like_to_view_ratio"] == 10.0

    def test_empty_reels(self) -> None:
        result = analyze_audience_behavior([])
        assert result == {}

    def test_zero_views_does_not_crash(self) -> None:
        reels = [{"views": 0, "likes": 0}]
        result = analyze_audience_behavior(reels)
        assert result == {}

    def test_some_reels_have_no_views(self) -> None:
        reels = [{"views": 0, "likes": 0}, {"views": 500, "likes": 25}]
        result = analyze_audience_behavior(reels)
        assert result["avg_views_per_reel"] == 500.0


class TestExtractInsights:
    def test_combines_all_analyses(self) -> None:
        reels = [
            {
                "intelligence": {"hook_type": "CURIOSITY", "narrative_style": "storytelling"},
                "metrics": {"engagement_rate": 10.0},
                "views": 1000,
                "likes": 100,
                "commentsCount": 10,
            }
        ]
        result = extract_insights(reels, min_reels=1)
        assert "winning_hooks_analysis" in result
        assert "narrative_patterns" in result
        assert "audience_behavior" in result
        assert "analyzed_at" in result
        assert result["reel_count"] == 1

    def test_empty_reels(self) -> None:
        result = extract_insights([])
        assert result["reel_count"] == 0
        assert result["winning_hooks_analysis"]["analysis_possible"] is False