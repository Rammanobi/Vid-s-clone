from __future__ import annotations

from typing import Any

from app.logging_setup import get_logger

logger = get_logger(__name__)


def _try_load_embedding_model() -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("sentence_transformer_model_loaded", model="all-MiniLM-L6-v2")
        return model
    except (ImportError, Exception) as exc:
        logger.warning("sentence_transformer_not_available", error=str(exc))
        return None


_embedding_model = _try_load_embedding_model()


def embedding_model_available() -> bool:
    return _embedding_model is not None


def embed_text(text: str) -> list[float] | None:
    if not text or not text.strip():
        return None

    if _embedding_model is None:
        logger.error("sentence_transformer_not_loaded, cannot embed text")
        return None

    try:
        vector = _embedding_model.encode(text)
        return vector.tolist()
    except Exception as exc:
        logger.error("embed_text_failed", error=str(exc))
        return None
