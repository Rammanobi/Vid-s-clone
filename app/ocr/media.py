from __future__ import annotations

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

    logger.debug("video_downloaded_for_ocr", path=str(tmp_path))
    return tmp_path


def cleanup(paths: list[Path]) -> None:
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass