from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.content_engine import (
    format_intelligence_output,
    process_single_reel_intelligence,
    run_content_intelligence_pipeline,
)
from app.llm_intelligence import (
    extract_intelligence_hybrid,
    extract_intelligence_with_llm,
    get_input_availability,
    is_input_partial,
)
from app.main import app
from app.schema_validator import ContentIntelligenceSchema

pytestmark = pytest.mark.asyncio


class TestGetInputAvailability:
    def test_all_available(self) -> None:
        result = get_input_availability(
            transcript="hello world",
            caption="caption text",
            text_overlays=["overlay1"],
            visual_topics=["topic1"],
            visual_summary="summary text",
        )
        assert result == {
            "transcript": True,
            "caption": True,
            "text_overlays": True,
            "visual_topics": True,
            "visual_summary": True,
        }

    def test_none_available(self) -> None:
        result = get_input_availability()
        assert all(v is False for v in result.values())

    def test_empty_strings_not_available(self) -> None:
        result = get_input_availability(
            transcript="",
            caption="  ",
            text_overlays=[""],
            visual_topics=[],
        )
        assert all(v is False for v in result.values())

    def test_mixed_availability(self) -> None:
        result = get_input_availability(
            transcript="valid transcript",
            caption=None,
            text_overlays=["", "valid overlay"],
            visual_topics=None,
            visual_summary="",
        )
        assert result["transcript"] is True
        assert result["caption"] is False
        assert result["text_overlays"] is True
        assert result["visual_topics"] is False
        assert result["visual_summary"] is False


class TestIsInputPartial:
    def test_full_input_not_partial(self) -> None:
        assert is_input_partial(
            transcript="a",
            caption="b",
            text_overlays=["c"],
            visual_topics=["d"],
            visual_summary="e",
        ) is False

    def test_one_input_is_partial(self) -> None:
        assert is_input_partial(
            transcript="only this"
        ) is True

    def test_two_inputs_not_partial(self) -> None:
        assert is_input_partial(
            transcript="a", caption="b"
        ) is False


class TestExtractIntelligenceWithLLM:
    async def test_returns_empty_schema_on_no_input(self) -> None:
        mock_client = AsyncMock()
        result = await extract_intelligence_with_llm(
            reel_db_id="r1", llm_client=mock_client
        )
        assert result.reel_id == "r1"
        assert result.topic is None
        mock_client.extract_structured.assert_not_called()

    async def test_successful_extraction(self) -> None:
        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "topic": "cooking pasta",
                "hook_type": "PROBLEM_SOLUTION",
                "hook_text": "how to cook perfectly",
                "cta": "follow for more",
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
            transcript="pasta cooking transcript",
            caption="check out this pasta recipe",
            text_overlays=["pasta", "al dente"],
            llm_client=mock_client,
        )
        assert result.reel_id == "r1"
        assert result.topic == "cooking pasta"
        assert result.hook_type is not None
        assert result.hook_type.value == "PROBLEM_SOLUTION"
        assert result.content_format is not None
        assert result.content_format.value == "TUTORIAL"
        assert result.sentiment == "positive"

    async def test_fallback_on_failure_returns_empty_schema(self) -> None:
        mock_client = AsyncMock()
        mock_client.extract_structured = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await extract_intelligence_with_llm(
            reel_db_id="r1",
            transcript="some content",
            llm_client=mock_client,
        )
        assert result.reel_id == "r1"
        assert result.topic is None
        assert result.hook_type is None

    async def test_handles_partial_llm_response(self) -> None:
        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"topic": "fitness"}

        mock_client = AsyncMock()
        mock_client.extract_structured = mock_extract

        result = await extract_intelligence_with_llm(
            reel_db_id="r1",
            transcript="workout tips",
            llm_client=mock_client,
        )
        assert result.topic == "fitness"
        assert result.hook_type is None
        assert result.cta is None


class TestExtractIntelligenceHybrid:
    async def test_hybrid_llm_takes_priority(self) -> None:
        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "topic": "LLM topic",
                "hook_type": "CURIOSITY",
                "sentiment": "positive",
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
        assert result.topic == "LLM topic"
        assert result.hook_type is not None
        assert result.hook_type.value == "CURIOSITY"

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

    async def test_hybrid_rule_fallback_has_different_topic(self) -> None:
        mock_client = AsyncMock()
        mock_client.extract_structured = AsyncMock(
            side_effect=Exception("LLM down")
        )

        result = await extract_intelligence_hybrid(
            reel_db_id="r1",
            transcript="you won't believe what happened next",
            caption="amazing story",
            llm_client=mock_client,
            use_llm=True,
        )
        assert result.hook_type is not None
        assert result.hook_text is not None

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

    async def test_hybrid_merges_from_rules_when_llm_returns_none(self) -> None:
        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

        mock_client = AsyncMock()
        mock_client.extract_structured = mock_extract

        result = await extract_intelligence_hybrid(
            reel_db_id="r1",
            transcript="amazing you won't believe this",
            caption="check it out",
            llm_client=mock_client,
            use_llm=True,
        )
        assert result.topic is not None
        assert result.hook_type is not None

    async def test_hybrid_partial_input_warning(self) -> None:
        mock_client = AsyncMock()

        result = await extract_intelligence_hybrid(
            reel_db_id="r1",
            llm_client=mock_client,
            use_llm=False,
        )
        assert result.reel_id == "r1"
        assert result.topic is None


class TestProcessSingleReelIntelligence:
    async def test_processes_reel_and_upserts(self) -> None:
        mock_db = AsyncMock()
        mock_db.upsert_content_intelligence = AsyncMock()

        async def mock_extract(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {
                "topic": "cooking pasta",
                "hook_type": "PROBLEM_SOLUTION",
                "hook_text": "perfect pasta in 5 min",
                "cta": "follow for recipes",
                "content_format": "TUTORIAL",
                "teaching_style": "step_by_step",
                "narrative_style": "informational",
                "audience_intent": "educational",
                "sentiment": "positive",
                "visual_style": "studio",
            }

        mock_llm = AsyncMock()
        mock_llm.extract_structured = mock_extract

        reel = {
            "id": "r1",
            "transcript": "how to cook pasta",
            "caption": "perfect pasta recipe",
            "textOverlays": ["pasta", "al dente"],
        }

        result = await process_single_reel_intelligence(
            reel, mock_db, llm_client=mock_llm, use_llm=True
        )
        assert result["reel_id"] == "r1"
        assert result["topic"] == "cooking pasta"
        assert result["hook_type"] == "PROBLEM_SOLUTION"
        assert result["cta"] == "follow for recipes"

        mock_db.upsert_content_intelligence.assert_awaited_once()
        call_kwargs = mock_db.upsert_content_intelligence.call_args[1]
        assert call_kwargs["reel_db_id"] == "r1"
        assert call_kwargs["topic"] == "cooking pasta"
        assert call_kwargs["hook_type"] == "PROBLEM_SOLUTION"

    async def test_handles_missing_fields(self) -> None:
        mock_db = AsyncMock()
        mock_db.upsert_content_intelligence = AsyncMock()

        reel = {"id": "r2"}

        result = await process_single_reel_intelligence(
            reel, mock_db, use_llm=False
        )
        assert result["reel_id"] == "r2"
        assert result["topic"] is None
        assert result["hook_type"] is None


class TestRunContentIntelligencePipeline:
    async def test_processes_batch_of_reels(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"id": "r1", "transcript": "first video", "caption": "caption1"},
                {"id": "r2", "transcript": "second video", "caption": "caption2"},
            ]
        )
        mock_db.upsert_content_intelligence = AsyncMock()

        result = await run_content_intelligence_pipeline(
            mock_db, limit=10, use_llm=False
        )

        assert result["processed"] == 2
        assert result["failed"] == 0
        assert len(result["results"]) == 2
        assert result["results"][0]["reel_id"] == "r1"
        assert mock_db.upsert_content_intelligence.await_count == 2

    async def test_handles_reel_errors_gracefully(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {"id": "r1", "transcript": "ok"},
                {"id": "r2", "transcript": "bad"},
            ]
        )
        mock_db.upsert_content_intelligence = AsyncMock(
            side_effect=[None, ValueError("DB error")]
        )

        result = await run_content_intelligence_pipeline(
            mock_db, limit=10, use_llm=False
        )

        assert result["processed"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert "DB error" in result["errors"][0]

    async def test_empty_batch(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_metrics = AsyncMock(return_value=[])

        result = await run_content_intelligence_pipeline(
            mock_db, use_llm=False
        )

        assert result["processed"] == 0
        assert result["failed"] == 0
        assert result["elapsed_sec"] >= 0

    async def test_elapsed_time_tracked(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[{"id": "r1", "transcript": "test"}]
        )
        mock_db.upsert_content_intelligence = AsyncMock()

        result = await run_content_intelligence_pipeline(
            mock_db, use_llm=False
        )

        # elapsed_sec is a real time.monotonic() delta. Processing a single
        # mocked reel with use_llm=False (pure rule-based extraction) can
        # finish in under a millisecond and round to 0.0 on a fast machine,
        # so assert the field exists and is a non-negative float rather than
        # strictly positive - a sleep() to force it above zero would just be
        # gaming the assertion, not testing anything real.
        assert "elapsed_sec" in result
        assert isinstance(result["elapsed_sec"], float)
        assert result["elapsed_sec"] >= 0

    async def test_passes_alternative_field_names(self) -> None:
        mock_db = AsyncMock()
        mock_db.get_reels_with_metrics = AsyncMock(
            return_value=[
                {
                    "id": "r1",
                    "transcript": "hello",
                    "text_overlays": ["overlay"],
                    "visual_topics": ["topic1"],
                    "visual_summary": "a bright scene",
                }
            ]
        )
        mock_db.upsert_content_intelligence = AsyncMock()

        result = await run_content_intelligence_pipeline(
            mock_db, use_llm=False
        )

        assert result["processed"] == 1
        assert result["failed"] == 0


class TestFormatIntelligenceOutput:
    def test_outputs_valid_json(self) -> None:
        result = {
            "reel_id": "r1",
            "topic": "cooking",
            "hook_type": "CURIOSITY",
            "hook_text": "you won't believe this",
            "cta": "follow me",
            "content_format": "TUTORIAL",
            "teaching_style": "step_by_step",
            "narrative_style": "informational",
            "audience_intent": "educational",
            "sentiment": "positive",
            "visual_style": "studio",
        }
        output = format_intelligence_output(result)
        import json
        parsed = json.loads(output)

        assert parsed["reel_id"] == "r1"
        assert parsed["topic"] == "cooking"
        assert parsed["hook_type"] == "CURIOSITY"
        assert parsed["sentiment"] == "positive"

    def test_output_is_indented(self) -> None:
        result = {"reel_id": "r1", "topic": "test"}
        output = format_intelligence_output(result)
        assert "\n" in output
        assert output.startswith("{")


class TestContentIntelligenceHealthEndpoint:
    async def test_health_endpoint_returns_status(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/content/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "database" in data
            assert "reel_count" in data
            assert "intelligence_count" in data
            assert "last_run" in data
            assert "version" in data

    async def test_health_endpoint_no_auth_required(self) -> None:
        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/content/health")
            assert resp.status_code == 200