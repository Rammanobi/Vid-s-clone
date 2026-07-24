from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.transcription.models import TranscriptResult, TranscriptSegment
from app.transcription.vad import _SPEECH_PROB_THRESHOLD, get_speech_score


class TestTranscriptModels:
    def test_valid_segment(self) -> None:
        seg = TranscriptSegment(
            start=0.0, end=2.5, text="hello world", chunk_id="abc"
        )
        assert seg.start == 0.0
        assert seg.end == 2.5
        assert seg.text == "hello world"
        assert seg.chunk_id == "abc"

    def test_segment_negative_start_fails(self) -> None:
        with pytest.raises(ValueError):
            TranscriptSegment(
                start=-1.0, end=2.0, text="fail", chunk_id="x"
            )

    def test_segment_zero_end_fails(self) -> None:
        with pytest.raises(ValueError):
            TranscriptSegment(
                start=0.0, end=0.0, text="fail", chunk_id="x"
            )

    def test_segment_empty_text_fails(self) -> None:
        with pytest.raises(ValueError):
            TranscriptSegment(
                start=0.0, end=1.0, text="", chunk_id="x"
            )

    def test_transcript_result(self) -> None:
        seg = TranscriptSegment(
            start=0.0, end=1.0, text="hi", chunk_id="c1"
        )
        result = TranscriptResult(
            segments=[seg], full_text="hi", language="en"
        )
        assert result.language == "en"
        assert result.full_text == "hi"

    def test_segment_model_dump(self) -> None:
        seg = TranscriptSegment(
            start=0.0, end=2.5, text="hello", chunk_id="abc-123"
        )
        dumped = seg.model_dump()
        assert dumped["start"] == 0.0
        assert dumped["end"] == 2.5
        assert dumped["text"] == "hello"
        assert dumped["chunk_id"] == "abc-123"


class TestVAD:
    def test_speech_score_no_audio(self) -> None:
        score = get_speech_score(b"")
        assert score == 0.0

    def test_speech_score_valid_wave_no_speech(self) -> None:
        score = get_speech_score(_build_silent_wav(duration_sec=0.5))
        assert 0.0 <= score <= 1.0

    def test_speech_score_valid_wave_with_speech(self) -> None:
        score = get_speech_score(_build_tone_wav(duration_sec=0.5))
        assert 0.0 <= score <= 1.0


class TestTranscribeEdgeCases:
    @patch("app.transcription.whisper._whisper_model", None)
    def test_transcribe_no_model(self) -> None:
        from app.transcription.whisper import transcribe

        result = transcribe("fake.wav")
        assert result is None

    @patch("app.transcription.whisper._whisper_model")
    def test_transcribe_returns_segments(self, mock_model: MagicMock) -> None:
        from app.transcription.whisper import transcribe

        mock_segments = [
            MagicMock(start=0.0, end=1.5, text="hello"),
            MagicMock(start=1.5, end=3.0, text="world"),
        ]
        mock_info = MagicMock(language="en", duration=3.0)

        mock_model.transcribe.return_value = (iter(mock_segments), mock_info)

        result = transcribe("test.wav")
        assert result is not None
        assert result.language == "en"
        assert len(result.segments) == 2
        assert result.segments[0].text == "hello"
        assert result.segments[1].text == "world"
        assert result.full_text == "hello world"

    @patch("app.transcription.whisper._whisper_model")
    def test_transcribe_empty_segments(self, mock_model: MagicMock) -> None:
        from app.transcription.whisper import transcribe

        mock_info = MagicMock(language="en", duration=0.0)
        mock_model.transcribe.return_value = (iter([]), mock_info)

        result = transcribe("test.wav")
        assert result is None

    @patch("app.transcription.whisper._whisper_model")
    def test_transcribe_exception(self, mock_model: MagicMock) -> None:
        from app.transcription.whisper import transcribe

        mock_model.transcribe.side_effect = RuntimeError("model crash")

        result = transcribe("test.wav")
        assert result is None


class TestProcessorEdgeCases:
    @patch("app.transcription.processor.download_video", new_callable=AsyncMock)
    @patch("app.transcription.processor.extract_audio")
    @patch("app.transcription.processor.get_speech_score")
    def test_no_speech_returns_none(
        self,
        mock_speech: MagicMock,
        mock_extract: MagicMock,
        mock_download: AsyncMock,
    ) -> None:
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_speech.return_value = 0.0

        from app.transcription.processor import process_video

        result = None

        async def run() -> None:
            nonlocal result
            result = await process_video("https://example.com/video.mp4")

        import asyncio
        asyncio.run(run())

        assert result is None

    @patch("app.transcription.processor.download_video", new_callable=AsyncMock)
    @patch("app.transcription.processor.extract_audio")
    @patch("app.transcription.processor.get_speech_score")
    @patch("app.transcription.processor.transcribe")
    def test_transcription_success(
        self,
        mock_transcribe: MagicMock,
        mock_speech: MagicMock,
        mock_extract: MagicMock,
        mock_download: AsyncMock,
    ) -> None:
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_speech.return_value = 0.8

        mock_result = TranscriptResult(
            segments=[
                TranscriptSegment(
                    start=0.0, end=1.0, text="hello", chunk_id="c1"
                )
            ],
            full_text="hello",
            language="en",
        )
        mock_transcribe.return_value = mock_result

        from app.transcription.processor import process_video

        result = None

        async def run() -> None:
            nonlocal result
            result = await process_video("https://example.com/video.mp4")

        import asyncio
        asyncio.run(run())

        assert result is not None
        assert result["transcript"] == "hello"
        assert len(result["transcript_json"]) == 1
        assert result["transcript_json"][0]["text"] == "hello"
        assert result["transcript_json"][0]["chunk_id"] == "c1"

    @patch("app.transcription.processor.download_video", new_callable=AsyncMock)
    def test_download_failure_returns_none(
        self, mock_download: AsyncMock
    ) -> None:
        mock_download.side_effect = RuntimeError("network error")

        from app.transcription.processor import process_video

        result = None

        async def run() -> None:
            nonlocal result
            result = await process_video("https://example.com/video.mp4")

        import asyncio
        asyncio.run(run())

        assert result is None


def _build_silent_wav(duration_sec: float, sample_rate: int = 16000) -> bytes:
    import struct
    import wave
    import io
    buf = io.BytesIO()
    n_frames = int(sample_rate * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def _build_tone_wav(duration_sec: float, sample_rate: int = 16000) -> bytes:
    import struct
    import wave
    import io
    import math
    buf = io.BytesIO()
    n_frames = int(sample_rate * duration_sec)
    samples = []
    for i in range(n_frames):
        val = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        samples.append(struct.pack("<h", val))
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(samples))
    return buf.getvalue()