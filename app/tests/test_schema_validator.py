from __future__ import annotations

import pytest

from app.schema_validator import (
    ContentFormat,
    ContentIntelligenceSchema,
    HookType,
    MetricQuality,
    ReelUpdateSchema,
)


class TestReelUpdateSchema:
    def test_valid_full_schema(self) -> None:
        schema = ReelUpdateSchema(
            transcript="hello world",
            transcript_json=[
                {
                    "start": 0.0,
                    "end": 1.5,
                    "text": "hello",
                    "chunk_id": "c1",
                }
            ],
            text_overlays=["Hello", "World"],
            visual_topics=["person talking"],
            visual_summary="person talking (45%)",
            combined_embedding=[0.1] * 1536,
        )
        assert schema.transcript == "hello world"
        assert len(schema.transcript_json) == 1
        assert len(schema.combined_embedding) == 1536

    def test_minimal_schema(self) -> None:
        schema = ReelUpdateSchema()
        assert schema.transcript is None
        assert schema.transcript_json is None
        assert schema.text_overlays == []
        assert schema.visual_topics == []
        assert schema.visual_summary is None
        assert schema.combined_embedding is None

    def test_embedding_wrong_size_fails(self) -> None:
        with pytest.raises(ValueError):
            ReelUpdateSchema(combined_embedding=[0.1] * 100)

    def test_transcript_segment_missing_fields(self) -> None:
        with pytest.raises(ValueError, match="missing required fields"):
            ReelUpdateSchema(
                transcript_json=[{"start": 0.0, "text": "hello"}]
            )

    def test_transcript_segment_negative_start(self) -> None:
        with pytest.raises(ValueError, match="must be >= 0"):
            ReelUpdateSchema(
                transcript_json=[
                    {
                        "start": -1.0,
                        "end": 1.0,
                        "text": "bad",
                        "chunk_id": "c1",
                    }
                ]
            )

    def test_transcript_segment_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="must be > start"):
            ReelUpdateSchema(
                transcript_json=[
                    {
                        "start": 2.0,
                        "end": 1.0,
                        "text": "bad",
                        "chunk_id": "c1",
                    }
                ]
            )

    def test_transcript_segment_empty_text(self) -> None:
        with pytest.raises(ValueError, match="must be non-empty"):
            ReelUpdateSchema(
                transcript_json=[
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "text": "",
                        "chunk_id": "c1",
                    }
                ]
            )

    def test_transcript_segment_missing_chunk_id(self) -> None:
        with pytest.raises(ValueError, match="missing chunk_id"):
            ReelUpdateSchema(
                transcript_json=[
                    {"start": 0.0, "end": 1.0, "text": "hello"}
                ]
            )


class TestContentIntelligenceSchema:
    def test_valid_full(self) -> None:
        ci = ContentIntelligenceSchema(
            reel_id="abc-123",
            topic="cooking tutorial",
            hook_type=HookType.PROBLEM_SOLUTION,
            hook_text="how to cook pasta",
            cta="follow for more",
            content_format=ContentFormat.TUTORIAL,
            teaching_style="Step-by-step",
            narrative_style="Storytelling",
            audience_intent="Educational",
            sentiment="positive",
            visual_style="Indoor",
        )
        assert ci.reel_id == "abc-123"
        assert ci.topic == "cooking tutorial"
        assert ci.hook_type == HookType.PROBLEM_SOLUTION
        assert ci.content_format == ContentFormat.TUTORIAL
        assert ci.sentiment == "positive"

    def test_minimal(self) -> None:
        ci = ContentIntelligenceSchema(reel_id="abc")
        assert ci.reel_id == "abc"
        assert ci.topic is None
        assert ci.hook_type is None
        assert ci.cta is None

    def test_reel_id_required(self) -> None:
        with pytest.raises(ValueError):
            ContentIntelligenceSchema()


class TestEnums:
    def test_hook_type_values(self) -> None:
        assert HookType.CURIOSITY.value == "CURIOSITY"
        assert HookType.QUESTION.value == "QUESTION"
        assert HookType.OTHER.value == "OTHER"

    def test_content_format_values(self) -> None:
        assert ContentFormat.TUTORIAL.value == "TUTORIAL"
        assert ContentFormat.SKIT.value == "SKIT"

    def test_metric_quality_values(self) -> None:
        assert MetricQuality.FULL.value == "FULL"
        assert MetricQuality.PARTIAL.value == "PARTIAL"