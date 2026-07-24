from __future__ import annotations

from app.intelligence import extract_intelligence
from app.schema_validator import ContentFormat, HookType


class TestExtractIntelligence:
    def test_minimal_input(self) -> None:
        result = extract_intelligence(reel_db_id="r1")
        assert result.reel_id == "r1"
        assert result.topic is None
        assert result.hook_type is None
        assert result.cta is None

    def test_topic_from_visual_topics(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            visual_topics=["person talking", "indoor setting"],
        )
        assert result.topic is not None
        assert "person talking" in result.topic

    def test_topic_from_transcript(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="this is a great cooking tutorial for pasta",
        )
        assert result.topic is not None
        words_in_topic = result.topic.lower().split("; ")
        first_word = words_in_topic[0].strip()
        assert first_word in ["this", "great", "cooking", "tutorial", "pasta"]

    def test_hook_curiosity(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="you won't believe what happened next",
        )
        assert result.hook_type == HookType.CURIOSITY
        assert result.hook_text is not None

    def test_hook_question(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="why do cats always land on their feet?",
        )
        assert result.hook_type == HookType.QUESTION

    def test_hook_problem_solution(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="here's how to fix your broken sink in 5 minutes",
        )
        assert result.hook_type == HookType.PROBLEM_SOLUTION

    def test_hook_contrarian(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="this is my unpopular opinion about social media",
        )
        assert result.hook_type == HookType.CONTRARIAN

    def test_hook_story(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="let me tell you a story about when I started my business",
        )
        assert result.hook_type == HookType.STORY

    def test_cta_detected(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="if you enjoyed this, please follow for more content",
        )
        assert result.cta is not None
        assert "follow" in result.cta.lower()

    def test_content_format_tutorial(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="step by step guide to baking bread",
            visual_topics=["person talking", "indoor setting"],
        )
        assert result.content_format == ContentFormat.TUTORIAL

    def test_content_format_talking_head(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            visual_topics=["person talking", "close up face"],
        )
        assert result.content_format == ContentFormat.TALKING_HEAD

    def test_content_format_skit(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="funny skit about office life",
            visual_topics=["group of people"],
        )
        assert result.content_format == ContentFormat.SKIT

    def test_sentiment_positive(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="this amazing product is absolutely incredible and beautiful",
        )
        assert result.sentiment == "positive"

    def test_sentiment_negative(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="this is the worst terrible awful product I've ever seen",
        )
        assert result.sentiment == "negative"

    def test_sentiment_neutral(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="here is a tutorial on how to learn the basics",
        )
        assert result.sentiment == "neutral" or result.sentiment == "positive"

    def test_teaching_style_step_by_step(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="first do this, next do that, then finally do this",
        )
        assert result.teaching_style == "Step-by-step"

    def test_teaching_style_explanatory(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="let me explain how it works because the reason is simple",
        )
        assert result.teaching_style == "Explanatory"

    def test_narrative_style_storytelling(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="let me tell you what happened to me last week",
        )
        assert result.narrative_style == "Storytelling"

    def test_audience_intent_educational(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="today you will learn how to understand this concept",
        )
        assert result.audience_intent == "Educational"

    def test_visual_style_outdoor(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            visual_topics=["outdoor setting", "nature landscape"],
        )
        assert result.visual_style is not None
        assert "Outdoor" in result.visual_style

    def test_visual_style_text_heavy(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            visual_topics=["text on screen"],
        )
        assert result.visual_style is not None
        assert "Text-heavy" in result.visual_style


class TestExtractIntelligenceEdgeCases:
    def test_combined_text_from_all_sources(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="hello from transcript",
            caption="hello from caption",
            text_overlays=["hello from overlay"],
            visual_topics=["person talking"],
        )
        assert result.topic is not None

    def test_hook_not_detected(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="the weather today is quite pleasant",
        )
        assert result.hook_type is None
        assert result.hook_text is None

    def test_cta_not_detected(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            transcript="the weather today is quite pleasant",
        )
        assert result.cta is None

    def test_overlays_boost_topic(self) -> None:
        result = extract_intelligence(
            reel_db_id="r1",
            text_overlays=["cooking", "recipe", "delicious"],
        )
        assert result.topic is not None