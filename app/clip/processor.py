from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from app.logging_setup import get_logger

logger = get_logger(__name__)

_VISUAL_TOPIC_CANDIDATES = [
    "person talking", "person presenting", "person exercising",
    "text on screen", "product showcase", "food and cooking",
    "travel and outdoors", "nature landscape", "city streets",
    "technology and gadgets", "animals and pets", "art and drawing",
    "music and dancing", "sports and athletics", "fashion and style",
    "beauty and makeup", "gaming", "animation", "indoor setting",
    "outdoor setting", "close up face", "group of people",
    "sunset or sunrise", "night scene", "underwater",
]

_OPENCLIP_MODEL_NAME = "ViT-B-16-SigLIP"
_OPENCLIP_PRETRAINED = "webli"


def _try_load_openclip() -> Any:
    try:
        import open_clip  # type: ignore[import-untyped]
        import torch  # type: ignore[import-untyped]

        model, _, preprocess = open_clip.create_model_and_transforms(
            _OPENCLIP_MODEL_NAME,
            pretrained=_OPENCLIP_PRETRAINED,
        )
        model.eval()
        tokenizer = open_clip.get_tokenizer(_OPENCLIP_MODEL_NAME)
        logger.info(
            "open_clip_loaded",
            model=_OPENCLIP_MODEL_NAME,
            pretrained=_OPENCLIP_PRETRAINED,
        )
        return {"model": model, "preprocess": preprocess, "tokenizer": tokenizer}
    except (ImportError, Exception) as exc:
        logger.warning("open_clip not available", error=str(exc))
        return None


_clip = _try_load_openclip()


def openclip_available() -> bool:
    return _clip is not None


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude == 0.0:
        return vector
    return [v / magnitude for v in vector]


def generate_frame_embedding(
    frame: np.ndarray,
) -> list[float] | None:
    if _clip is None:
        return None

    try:
        import torch  # type: ignore[import-untyped]
        from PIL import Image

        model = _clip["model"]
        preprocess = _clip["preprocess"]

        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image_tensor = preprocess(pil_image).unsqueeze(0)

        with torch.no_grad():
            embedding = model.encode_image(image_tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)

        return embedding.squeeze().tolist()

    except Exception as exc:
        logger.warning("frame_embedding_failed", error=str(exc))
        return None


def classify_topics(
    frame: np.ndarray,
) -> tuple[list[str], str]:
    if _clip is None:
        return [], ""

    try:
        import torch  # type: ignore[import-untyped]
        from PIL import Image

        model = _clip["model"]
        preprocess = _clip["preprocess"]
        tokenizer = _clip["tokenizer"]

        pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image_tensor = preprocess(pil_image).unsqueeze(0)
        text_tokens = tokenizer(_VISUAL_TOPIC_CANDIDATES)

        with torch.no_grad():
            image_features = model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            text_features = model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            scores = similarity.squeeze().tolist()

        if isinstance(scores, float):
            scores = [scores]

        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)

        top_topics: list[str] = []
        top_summary_parts: list[str] = []

        for idx, score in indexed[:5]:
            if score > 0.01:
                top_topics.append(_VISUAL_TOPIC_CANDIDATES[idx])
                top_summary_parts.append(
                    f"{_VISUAL_TOPIC_CANDIDATES[idx]} ({score:.1%})"
                )

        summary = "; ".join(top_summary_parts) if top_summary_parts else ""
        return top_topics, summary

    except Exception as exc:
        logger.warning("topic_classification_failed", error=str(exc))
        return [], ""