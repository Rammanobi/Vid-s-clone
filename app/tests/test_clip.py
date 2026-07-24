from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.clip.models import FrameEmbedding, VisualTopicResult
from app.clip.processor import _normalize, generate_frame_embedding, openclip_available


class TestCLIPModels:
    def test_valid_frame_embedding(self) -> None:
        emb = FrameEmbedding(
            frame_index=0,
            embedding=[0.1] * 1536,
        )
        assert emb.frame_index == 0
        assert len(emb.embedding) == 1536

    def test_frame_embedding_wrong_size(self) -> None:
        with pytest.raises(ValueError):
            FrameEmbedding(frame_index=0, embedding=[0.1] * 100)

    def test_visual_topic_result(self) -> None:
        result = VisualTopicResult(
            topics=["person talking", "indoor setting"],
            visual_summary="person talking (45.2%); indoor setting (30.1%)",
            combined_embedding=[0.5] * 1536,
        )
        assert len(result.topics) == 2
        assert len(result.combined_embedding) == 1536


class TestNormalize:
    def test_normalize_unit_vector(self) -> None:
        v = [3.0, 4.0]
        n = _normalize(v)
        assert abs(sum(x * x for x in n) - 1.0) < 1e-6
        assert n[0] == 0.6
        assert n[1] == 0.8

    def test_normalize_zero_vector(self) -> None:
        v = [0.0, 0.0, 0.0]
        n = _normalize(v)
        assert n == [0.0, 0.0, 0.0]

    def test_normalize_negative_values(self) -> None:
        v = [-3.0, -4.0]
        n = _normalize(v)
        magnitude = sum(x * x for x in n)
        assert abs(magnitude - 1.0) < 1e-6
        assert n[0] < 0
        assert n[1] < 0

    def test_normalize_single_element(self) -> None:
        v = [5.0]
        n = _normalize(v)
        assert n == [1.0]

    def test_normalize_already_unit(self) -> None:
        v = [1.0, 0.0]
        n = _normalize(v)
        assert n[0] == 1.0
        assert n[1] == 0.0


class TestFrameEmbedding:
    def test_no_clip_model(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("app.clip.processor._clip", None):
            result = generate_frame_embedding(frame)
            assert result is None

    def test_clip_exception(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_clip = {
            "model": MagicMock(),
            "preprocess": MagicMock(side_effect=RuntimeError("fail")),
            "tokenizer": MagicMock(),
        }
        with patch("app.clip.processor._clip", mock_clip):
            result = generate_frame_embedding(frame)
            assert result is None

    def test_openclip_not_available(self) -> None:
        with patch("app.clip.processor._clip", None):
            assert not openclip_available()


class TestExtractorEdgeCases:
    @pytest.mark.asyncio
    @patch("app.clip.extractor.openclip_available")
    async def test_clip_not_available(self, mock_available: MagicMock) -> None:
        mock_available.return_value = False

        from app.clip.extractor import extract_visual_features

        result = await extract_visual_features("https://example.com/vid.mp4")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    @patch("app.clip.extractor.openclip_available")
    @patch("app.clip.extractor.download_video", new_callable=AsyncMock)
    @patch("app.clip.extractor.sample_frames")
    async def test_no_frames(
        self,
        mock_sample: MagicMock,
        mock_download: AsyncMock,
        mock_available: MagicMock,
    ) -> None:
        from pathlib import Path

        mock_available.return_value = True
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_sample.return_value = []

        from app.clip.extractor import extract_visual_features

        result = await extract_visual_features("https://example.com/vid.mp4")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.clip.extractor.openclip_available")
    @patch("app.clip.extractor.download_video", new_callable=AsyncMock)
    @patch("app.clip.extractor.sample_frames")
    @patch("app.clip.extractor.generate_frame_embedding")
    async def test_embedding_failure(
        self,
        mock_embed: MagicMock,
        mock_sample: MagicMock,
        mock_download: AsyncMock,
        mock_available: MagicMock,
    ) -> None:
        from pathlib import Path

        mock_available.return_value = True
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_sample.return_value = [np.zeros((100, 100, 3), dtype=np.uint8)]
        mock_embed.return_value = None

        from app.clip.extractor import extract_visual_features

        result = await extract_visual_features("https://example.com/vid.mp4")
        assert result is None

    @patch("app.clip.extractor.openclip_available")
    def test_with_pre_supplied_frames(
        self,
        mock_available: MagicMock,
    ) -> None:
        mock_available.return_value = True

        from app.clip.extractor import extract_visual_features

        frames = [np.zeros((100, 100, 3), dtype=np.uint8)]
        result = None

        async def run() -> None:
            nonlocal result
            with (
                patch("app.clip.extractor.generate_frame_embedding") as mock_embed,
                patch("app.clip.extractor.classify_topics") as mock_topics,
            ):
                mock_embed.return_value = [0.1] * 1536
                mock_topics.return_value = (["person talking"], "person talking")

                result = await extract_visual_features(
                    "https://example.com/vid.mp4",
                    frames=frames,
                )

        import asyncio
        asyncio.run(run())

        assert result is not None
        assert len(result["combined_embedding"]) == 1536
        assert "person talking" in result["visual_topics"]