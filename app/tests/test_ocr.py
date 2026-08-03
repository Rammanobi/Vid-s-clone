from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from app.ocr.processor import deduplicate, merge_frame_texts, ocr_frame, sample_frames


class TestFrameSampling:
    def test_sample_frames_empty_video(self) -> None:
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = False
            mock_cap.return_value = mock_instance

            frames = sample_frames(Path("/fake/video.mp4"))
            assert frames == []

    def test_sample_frames_with_frames(self) -> None:
        with (
            patch("cv2.VideoCapture") as mock_cap,
        ):
            mock_instance = MagicMock()
            mock_instance.isOpened.return_value = True
            mock_instance.get.return_value = 30.0

            read_results = [(True, np.zeros((100, 100, 3), dtype=np.uint8))] * 60
            mock_instance.read.side_effect = read_results + [(False, None)]
            mock_cap.return_value = mock_instance

            frames = sample_frames(Path("/fake/video.mp4"))
            assert len(frames) > 0


class TestOCROnFrame:
    @patch("app.ocr.processor._tesseract", None)
    def test_ocr_no_tesseract(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        texts = ocr_frame(frame)
        assert texts == []

    def test_ocr_empty_frame(self) -> None:
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_data.return_value = {
            "text": [],
            "conf": [],
        }

        with patch("app.ocr.processor._tesseract", mock_tesseract):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            texts = ocr_frame(frame)
            assert texts == []

    def test_ocr_detects_text(self) -> None:
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_data.return_value = {
            "text": ["Hello", "World", "", "Foo"],
            "conf": ["95", "80", "0", "50"],
        }
        mock_tesseract.Output.DICT = "dict"

        with patch("app.ocr.processor._tesseract", mock_tesseract):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            texts = ocr_frame(frame)
            assert "Hello" in texts
            assert "World" in texts
            assert "" not in texts

    def test_ocr_low_confidence_filtered(self) -> None:
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_data.return_value = {
            "text": ["Low", "High"],
            "conf": ["10", "95"],
        }
        mock_tesseract.Output.DICT = "dict"

        with patch("app.ocr.processor._tesseract", mock_tesseract):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            texts = ocr_frame(frame)
            assert "Low" not in texts
            assert "High" in texts

    def test_ocr_short_text_filtered(self) -> None:
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_data.return_value = {
            "text": ["A", "AB"],
            "conf": ["95", "95"],
        }
        mock_tesseract.Output.DICT = "dict"

        with patch("app.ocr.processor._tesseract", mock_tesseract):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            texts = ocr_frame(frame)
            assert "A" not in texts
            assert "AB" in texts

    def test_ocr_mixed_confidence(self) -> None:
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_data.return_value = {
            "text": ["Keep", "Discard", "KeepToo"],
            "conf": ["95", "5", "80"],
        }
        mock_tesseract.Output.DICT = "dict"

        with patch("app.ocr.processor._tesseract", mock_tesseract):
            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            texts = ocr_frame(frame)
            assert "Keep" in texts
            assert "Discard" not in texts
            assert "KeepToo" in texts


class TestDeduplicate:
    def test_removes_duplicates(self) -> None:
        texts = ["Hello", "hello", "HELLO", "World", "world"]
        result = deduplicate(texts)
        assert len(result) == 2

    def test_empty_list(self) -> None:
        assert deduplicate([]) == []

    def test_strips_whitespace(self) -> None:
        texts = ["  Hello  ", "hello"]
        result = deduplicate(texts)
        assert result == ["Hello"]

    def test_preserves_first_occurrence(self) -> None:
        texts = ["First", "second", "first"]
        result = deduplicate(texts)
        assert result[0] == "First"
        assert result[1] == "second"


class TestMergeFrameTexts:
    def test_merges_and_deduplicates(self) -> None:
        all_texts = [["Hello", "World"], ["World", "Foo"]]
        result = merge_frame_texts(all_texts)
        assert "Hello" in result
        assert "World" in result
        assert "Foo" in result
        assert len(result) == 3

    def test_empty_input(self) -> None:
        assert merge_frame_texts([]) == []

    def test_empty_frames(self) -> None:
        assert merge_frame_texts([[], [], []]) == []


class TestExtractorEdgeCases:
    @patch("app.ocr.extractor.download_video", new_callable=AsyncMock)
    @patch("app.ocr.extractor.tesseract_available")
    def test_no_tesseract_returns_empty(
        self, mock_available: MagicMock, mock_download: AsyncMock
    ) -> None:
        mock_available.return_value = False

        from app.ocr.extractor import extract_text_overlays

        result = None

        async def run() -> None:
            nonlocal result
            result = await extract_text_overlays("https://example.com/vid.mp4")

        import asyncio
        asyncio.run(run())

        assert result == []

    @patch("app.ocr.extractor.download_video", new_callable=AsyncMock)
    @patch("app.ocr.extractor.tesseract_available")
    def test_download_failure_returns_empty(
        self, mock_available: MagicMock, mock_download: AsyncMock
    ) -> None:
        mock_available.return_value = True
        mock_download.side_effect = RuntimeError("network error")

        from app.ocr.extractor import extract_text_overlays

        result = None

        async def run() -> None:
            nonlocal result
            result = await extract_text_overlays("https://example.com/vid.mp4")

        import asyncio
        asyncio.run(run())

        assert result == []