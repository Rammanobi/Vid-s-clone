from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.db import DatabaseClient
from app.embeddings import embed_text
from app.logging_setup import get_logger
from app.transcription.media import cleanup, download_video, extract_audio
from app.transcription.whisper import transcribe, whisper_available

logger = get_logger(__name__)

# Persistent local storage for downloaded reel video/audio, relative to repo
# root. Created lazily so importing this module never fails on a read-only
# or ephemeral filesystem until it's actually needed.
RECORDINGS_DIR = Path("data/reel_recordings")
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


async def transcribe_reel_on_demand(
    reel: dict[str, Any], db: DatabaseClient
) -> dict[str, Any]:
    """Download + transcribe a single reel on demand, persisting the media
    locally instead of cleaning it up. Skips re-work if a transcript already
    exists on the reel. Never raises - failures are returned as
    ``{"error": ...}`` so one bad reel doesn't block the others.
    """
    reel_id = reel.get("id")
    instagram_reel_id = reel.get("instagramReelId")
    video_url = reel.get("videoUrl")

    existing_transcript = reel.get("transcript")
    if existing_transcript:
        logger.info("on_demand_transcription_skipped", reel_id=reel_id)
        return {
            "reel_id": reel_id,
            "transcript": existing_transcript,
            "skipped": True,
        }

    if not video_url:
        return {
            "reel_id": reel_id,
            "error": "reel has no videoUrl",
            "skipped": False,
        }

    if not whisper_available():
        return {
            "reel_id": reel_id,
            "error": "faster-whisper not available",
            "skipped": False,
        }

    video_path: Path | None = None
    audio_path: Path | None = None

    try:
        video_path = await download_video(video_url)

        audio_fd, audio_path_str = tempfile.mkstemp(suffix=".wav")
        audio_path = Path(audio_path_str)
        extract_audio(video_path, audio_path)

        result = transcribe(str(audio_path))
        if result is None:
            return {
                "reel_id": reel_id,
                "error": "whisper produced no transcript",
                "skipped": False,
            }

        transcript_json = [seg.model_dump() for seg in result.segments]
        transcript = result.full_text

        dest_dir = RECORDINGS_DIR / (instagram_reel_id or str(reel_id))
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_video = dest_dir / "video.mp4"
        dest_audio = dest_dir / "audio.wav"
        shutil.copy2(video_path, dest_video)
        shutil.copy2(audio_path, dest_audio)

        await db.update_reel_transcript(
            reel_db_id=reel_id,
            transcript=transcript,
            transcript_json=transcript_json,
        )

        try:
            caption = reel.get("caption")
            embedding_text = f"{caption}. {transcript}" if caption else transcript
            embedding = embed_text(embedding_text)
            if embedding is not None:
                await db.update_reel_transcript_embedding(
                    reel_db_id=reel_id,
                    embedding=embedding,
                )
        except Exception as exc:
            logger.warning(
                "on_demand_transcript_embedding_failed",
                reel_id=reel_id,
                error=str(exc),
            )

        logger.info(
            "on_demand_transcription_complete",
            reel_id=reel_id,
            instagram_reel_id=instagram_reel_id,
        )

        return {
            "reel_id": reel_id,
            "instagram_reel_id": instagram_reel_id,
            "transcript": transcript,
            "video_path": str(dest_video),
            "audio_path": str(dest_audio),
            "skipped": False,
        }

    except Exception as exc:
        logger.error(
            "on_demand_transcription_failed",
            reel_id=reel_id,
            error=str(exc),
        )
        return {
            "reel_id": reel_id,
            "error": str(exc),
            "skipped": False,
        }

    finally:
        cleanup_paths = [p for p in [video_path, audio_path] if p is not None]
        cleanup(cleanup_paths)


async def ensure_reels_transcribed(
    db: DatabaseClient, count: int
) -> list[dict[str, Any]]:
    """Resolve the primary account, fetch its `count` most recent reels, and
    transcribe each on demand (sequentially - this is CPU-bound Whisper
    inference, not worth parallelizing for a first version). Never raises;
    if there's no primary account or fewer reels than requested, processes
    whatever actually exists.
    """
    account_id = await db.get_primary_account_id()
    if not account_id:
        logger.warning("ensure_reels_transcribed_no_primary_account")
        return []

    reels = await db.get_reels_by_account(account_id, limit=count)
    if len(reels) < count:
        logger.info(
            "ensure_reels_transcribed_fewer_reels_than_requested",
            requested=count,
            found=len(reels),
        )

    results: list[dict[str, Any]] = []
    for reel in reels:
        result = await transcribe_reel_on_demand(reel, db)
        results.append(result)

    return results


if __name__ == "__main__":
    # ponytail: real end-to-end verification - connects to the actual
    # configured Neon database, downloads a real reel video from its CDN URL
    # (not a Hiker API call - that URL is already stored from a prior
    # ingestion), and runs real Whisper inference. Signed CDN URLs can expire,
    # so an HTTP 403/410 here is an expected possible outcome, not a bug in
    # this module.
    import asyncio

    from app.config import settings

    async def _main() -> None:
        db = DatabaseClient(settings.database_url)
        await db.connect()
        try:
            results = await ensure_reels_transcribed(db, count=1)
            print(results)
        finally:
            await db.close()

    asyncio.run(_main())
