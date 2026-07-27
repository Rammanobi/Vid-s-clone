from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from app.logging_setup import get_logger

logger = get_logger(__name__)


async def download_video(video_url: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("GET", video_url) as response:
            response.raise_for_status()
            with open(tmp_path, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

    logger.debug("video_downloaded", path=str(tmp_path), url=video_url)
    return tmp_path


def extract_audio(video_path: Path, audio_path: Path) -> None:
    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        common_locations = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
        ]
        for loc in common_locations:
            if Path(loc).exists():
                ffmpeg_path = loc
                break

    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found in PATH or common locations")

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed: {result.stderr[:500]}"
        )
    logger.debug("audio_extracted", path=str(audio_path))


def cleanup(paths: list[Path]) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass