"""YouTube audio downloader using yt-dlp Python API.

Uses the yt-dlp library directly (no subprocess) for better
control over SSL, timeouts, and error handling.
"""

import asyncio
import logging
import ssl
from pathlib import Path
from functools import partial

from config import TEMP_DIR

logger = logging.getLogger(__name__)

# Download timeout
DOWNLOAD_TIMEOUT = 120


def _create_ydl_opts(output_template: str) -> dict:
    """Create yt-dlp options dict."""
    return {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "extractaudio": True,
        "audioformat": "mp3",
        "audioquality": "9",  # lowest quality = smallest file
        "max_filesize": 50 * 1024 * 1024,  # 50MB
        "socket_timeout": 30,
        "retries": 3,
        "nocheckcertificate": True,
        "legacy_server_connect": True,
        "quiet": True,
        "no_warnings": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "9",
        }],
    }


def _download_sync(url: str, output_template: str) -> str | None:
    """Synchronous download — runs in a thread pool."""
    import yt_dlp

    opts = _create_ydl_opts(output_template)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info:
            return ydl.prepare_filename(info)
    return None


def _get_info_sync(url: str) -> dict:
    """Synchronous info fetch — runs in a thread pool."""
    import yt_dlp

    opts = {
        "noplaylist": True,
        "nocheckcertificate": True,
        "legacy_server_connect": True,
        "socket_timeout": 15,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title", "Unknown") if info else "Unknown",
            "duration": info.get("duration", 0) if info else 0,
        }


async def download_youtube_audio(url: str) -> Path:
    """Download audio from a YouTube URL.

    Returns path to the downloaded audio file.
    """
    output_template = str(TEMP_DIR / "yt_%(id)s.%(ext)s")

    logger.info("Downloading YouTube audio: %s", url)

    loop = asyncio.get_event_loop()

    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_download_sync, url, output_template)),
            timeout=DOWNLOAD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"YouTube yuklab olish {DOWNLOAD_TIMEOUT} soniyadan oshdi. "
            "Video juda uzun yoki internet sekin bo'lishi mumkin."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error("yt-dlp error: %s", error_msg)
        raise RuntimeError(f"YouTube yuklab olishda xatolik: {error_msg[:200]}")

    # Use the result path from yt-dlp, adjusting extension for post-processing
    if result:
        result_path = Path(result)
        # yt-dlp reports original ext, but postprocessor converts to .mp3
        mp3_path = result_path.with_suffix(".mp3")
        if mp3_path.exists():
            logger.info("Downloaded: %s", mp3_path.name)
            return mp3_path
        # Fallback: check if original file exists
        if result_path.exists():
            logger.info("Downloaded (original): %s", result_path.name)
            return result_path

    # Last resort fallback: find most recent yt_* file
    mp3_files = sorted(
        TEMP_DIR.glob("yt_*.mp3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if mp3_files:
        logger.info("Downloaded (fallback): %s", mp3_files[0].name)
        return mp3_files[0]

    raise RuntimeError("Yuklab olingan fayl topilmadi")


async def get_youtube_info(url: str) -> dict:
    """Get video title and duration without downloading."""
    loop = asyncio.get_event_loop()

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, partial(_get_info_sync, url)),
            timeout=30,
        )
    except (asyncio.TimeoutError, Exception):
        return {"title": "Unknown", "duration": 0}
