"""Instagram Reels audio downloader using yt-dlp Python API."""

import asyncio
import logging
from pathlib import Path
from functools import partial

from config import TEMP_DIR

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 90


def _download_sync(url: str, output_template: str) -> str | None:
    """Synchronous download — runs in a thread pool."""
    import yt_dlp

    opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "extractaudio": True,
        "audioformat": "mp3",
        "audioquality": "9",
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

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info:
            return ydl.prepare_filename(info)
    return None


async def download_instagram_audio(url: str) -> Path:
    """Download audio from an Instagram Reel URL.

    Returns path to the downloaded audio file.
    """
    output_template = str(TEMP_DIR / "ig_%(id)s.%(ext)s")

    logger.info("Downloading Instagram audio: %s", url)

    loop = asyncio.get_event_loop()

    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, partial(_download_sync, url, output_template)),
            timeout=DOWNLOAD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Instagram yuklab olish {DOWNLOAD_TIMEOUT} soniyadan oshdi."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error("yt-dlp (Instagram) error: %s", error_msg)
        raise RuntimeError(f"Instagram yuklab olishda xatolik: {error_msg[:200]}")

    # Find the downloaded file
    mp3_files = sorted(
        TEMP_DIR.glob("ig_*.mp3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if mp3_files:
        logger.info("Downloaded: %s", mp3_files[0].name)
        return mp3_files[0]

    audio_files = sorted(
        [f for f in TEMP_DIR.iterdir() if f.suffix in (".mp3", ".m4a", ".webm", ".opus")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if audio_files:
        return audio_files[0]

    raise RuntimeError("Yuklab olingan Instagram fayl topilmadi")
