from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from app.selector import (
    ModalityDecision,
    ModalityScores,
    compute_text_score,
    compute_visual_change_score,
    decide_modalities,
)


class TestModalityScores:
    def test_default_scores(self) -> None:
        s = ModalityScores()
        assert s.speech_score == 0.0
        assert s.text_score == 0.0
        assert s.visual_change_score == 0.0


class TestComputeTextScore:
    def test_no_frames(self) -> None:
        score = compute_text_score([], 0)
        assert score == 0.0

    def test_no_text(self) -> None:
        ocr_per_frame: list[list[str]] = [[], [], []]
        score = compute_text_score(ocr_per_frame, 3)
        assert score == 0.0

    def test_some_text(self) -> None:
        ocr_per_frame = [["Hello"], [], ["World"]]
        score = compute_text_score(ocr_per_frame, 3)
        ratio = 2 / 3
        density = 2 / 3
        expected = round(ratio * 0.6 + density * 0.4, 4)
        assert score == expected

    def test_all_text(self) -> None:
        ocr_per_frame = [["A", "B"], ["C"], ["D", "E", "F"]]
        score = compute_text_score(ocr_per_frame, 3)
        ratio = 3 / 3
        density = min(6 / 3, 1.0)
        expected = round(ratio * 0.6 + density * 0.4, 4)
        assert score == expected

    def test_density_capped(self) -> None:
        ocr_per_frame = [["A"] * 100]
        score = compute_text_score(ocr_per_frame, 1)
        assert score <= 1.0


class TestComputeVisualChangeScore:
    def test_less_than_two_frames(self) -> None:
        frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
        score = compute_visual_change_score(frames)
        assert score == 0.0

    def test_identical_frames(self) -> None:
        frame = np.ones((10, 10, 3), dtype=np.uint8) * 128
        frames = [frame, frame.copy()]
        score = compute_visual_change_score(frames)
        assert score == 0.0

    def test_different_frames(self) -> None:
        f1 = np.zeros((10, 10, 3), dtype=np.uint8)
        f2 = np.ones((10, 10, 3), dtype=np.uint8) * 255
        frames = [f1, f2]
        score = compute_visual_change_score(frames)
        assert score > 0.5

    def test_empty_list(self) -> None:
        assert compute_visual_change_score([]) == 0.0


class TestDecideModalities:
    def test_high_speech_runs_transcription(self) -> None:
        d = decide_modalities(speech_score=0.8, text_score=0.0, visual_change_score=0.0)
        assert d.run_transcription is True
        assert d.run_ocr is False
        assert d.run_clip is False

    def test_high_text_runs_ocr(self) -> None:
        d = decide_modalities(speech_score=0.0, text_score=0.8, visual_change_score=0.0)
        assert d.run_transcription is False
        assert d.run_ocr is True
        assert d.run_clip is False

    def test_high_visual_change_runs_clip(self) -> None:
        d = decide_modalities(speech_score=0.0, text_score=0.0, visual_change_score=0.3)
        assert d.run_transcription is False
        assert d.run_ocr is True
        assert d.run_clip is True

    def test_low_speech_triggers_ocr_fallback(self) -> None:
        d = decide_modalities(speech_score=0.0, text_score=0.0, visual_change_score=0.0)
        assert d.run_transcription is False
        assert d.run_ocr is True
        assert d.run_clip is True

    def test_all_high(self) -> None:
        d = decide_modalities(speech_score=0.9, text_score=0.9, visual_change_score=0.9)
        assert d.run_transcription is True
        assert d.run_ocr is True
        assert d.run_clip is True

    def test_custom_thresholds(self) -> None:
        d = decide_modalities(
            speech_score=0.05,
            text_score=0.05,
            visual_change_score=0.01,
            speech_threshold=0.1,
            text_threshold=0.1,
            visual_threshold=0.05,
        )
        assert d.run_transcription is False
        assert d.run_ocr is True
        assert d.run_clip is False

    def test_boundary_speech(self) -> None:
        d = decide_modalities(speech_score=0.1, text_score=0.0, visual_change_score=0.0)
        assert d.run_transcription is True

    def test_boundary_text(self) -> None:
        d = decide_modalities(speech_score=0.0, text_score=0.15, visual_change_score=0.0)
        assert d.run_ocr is True

    def test_scores_preserved_in_decision(self) -> None:
        d = decide_modalities(speech_score=0.5, text_score=0.3, visual_change_score=0.2)
        assert d.scores.speech_score == 0.5
        assert d.scores.text_score == 0.3
        assert d.scores.visual_change_score == 0.2


class TestDecisionEdgeCases:
    def test_zero_scores_fallback(self) -> None:
        d = decide_modalities(speech_score=0.0, text_score=0.0, visual_change_score=0.0)
        assert d.run_clip is True
        assert d.run_ocr is True

    def test_near_zero_not_fallback(self) -> None:
        d = decide_modalities(
            speech_score=0.01, text_score=0.01, visual_change_score=0.01
        )
        assert d.run_clip is False
        assert d.run_ocr is True
        assert d.run_transcription is False