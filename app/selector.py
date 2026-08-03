from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class ModalityScores:
    speech_score: float = 0.0
    text_score: float = 0.0
    visual_change_score: float = 0.0


@dataclass
class ModalityDecision:
    run_transcription: bool = False
    run_ocr: bool = False
    run_clip: bool = False
    scores: ModalityScores = field(default_factory=ModalityScores)


_SPEECH_THRESHOLD = 0.1
_TEXT_THRESHOLD = 0.15
_VISUAL_CHANGE_THRESHOLD = 0.05


def compute_text_score(
    ocr_per_frame: list[list[str]],
    frame_count: int,
) -> float:
    if frame_count == 0:
        return 0.0

    frames_with_text = sum(1 for texts in ocr_per_frame if texts)
    ratio = frames_with_text / frame_count

    total_texts = sum(len(texts) for texts in ocr_per_frame)
    density = min(total_texts / max(frame_count, 1), 1.0)

    return round((ratio * 0.6 + density * 0.4), 4)


def compute_visual_change_score(
    frames: list[np.ndarray],
) -> float:
    if len(frames) < 2:
        return 0.0

    diffs: list[float] = []
    for i in range(1, len(frames)):
        prev_gray = cv2.cvtColor(frames[i - 1], cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(prev_gray, curr_gray)
        mean_diff = float(np.mean(diff)) / 255.0
        diffs.append(mean_diff)

    if not diffs:
        return 0.0

    return round(float(np.mean(diffs)), 4)


def decide_modalities(
    speech_score: float,
    text_score: float,
    visual_change_score: float,
    speech_threshold: float = _SPEECH_THRESHOLD,
    text_threshold: float = _TEXT_THRESHOLD,
    visual_threshold: float = _VISUAL_CHANGE_THRESHOLD,
) -> ModalityDecision:
    scores = ModalityScores(
        speech_score=speech_score,
        text_score=text_score,
        visual_change_score=visual_change_score,
    )

    run_transcription = speech_score >= speech_threshold
    run_ocr = text_score >= text_threshold or speech_score < speech_threshold
    run_clip = visual_change_score >= visual_threshold

    if speech_score == 0.0 and text_score == 0.0 and visual_change_score == 0.0:
        run_clip = True

    decision = ModalityDecision(
        run_transcription=run_transcription,
        run_ocr=run_ocr,
        run_clip=run_clip,
        scores=scores,
    )

    logger.info(
        "modality_decision",
        speech_score=round(speech_score, 4),
        text_score=round(text_score, 4),
        visual_change_score=round(visual_change_score, 4),
        run_transcription=run_transcription,
        run_ocr=run_ocr,
        run_clip=run_clip,
    )

    return decision