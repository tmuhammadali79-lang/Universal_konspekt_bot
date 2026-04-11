"""Instagram Reels audio downloader using yt-dlp Python API."""

import asyncio
import logging
from pathlib import Path
from functools import partial

from config import TEMP_DIR

logger = logging.getLogger(__name__)

# Shorter timeout — Instagram often hangs or requires auth
DOWNLOAD_TIMEOUT = 45


def _download_sync(url: str, output_template: str) -> str | None:
    """Synchronous download — runs in a thread pool."""
    import yt_dlp

    opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "extractaudio": True,
        "audioformat": "mp3",
        "audioquality": "9",
        "socket_timeout": 15,          # shorter socket timeout
        "retries": 1,                  # fewer retries to fail faster
        "nocheckcertificate": True,
        "legacy_server_connect": True,
        "quiet": True,
        "no_warnings": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
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
    except (asyncio.TimeoutError, TimeoutError):
        raise RuntimeError(
            f"⏰ Instagram yuklab olish {DOWNLOAD_TIMEOUT} soniyadan oshdi.\n\n"
            "💡 Sabablari:\n"
            "• Instagram login talab qilishi mumkin\n"
            "• Video mavjud emas yoki yopiq profil\n"
            "• Internet sekin"
        )
    except Exception as e:
        error_msg = str(e)
        logger.error("yt-dlp (Instagram) error: %s", error_msg)

        # Provide user-friendly error messages
        if "login" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            raise RuntimeError(
                "🔒 Bu Instagram kontent login talab qiladi.\n\n"
                "💡 Iltimos, video/audio faylni yuklab olib, "
                "menga ovozli xabar sifatida yuboring."
            )
        raise RuntimeError(f"Instagram yuklab olishda xatolik: {error_msg[:200]}")

    # Use the result path from yt-dlp, adjusting extension for post-processing
    if result:
        result_path = Path(result)
        # yt-dlp reports original ext, but postprocessor converts to .mp3
        mp3_path = result_path.with_suffix(".mp3")
        if mp3_path.exists():
            logger.info("Downloaded: %s", mp3_path.name)
            return mp3_path
        if result_path.exists():
            logger.info("Downloaded (original): %s", result_path.name)
            return result_path

    # Last resort fallback
    mp3_files = sorted(
        TEMP_DIR.glob("ig_*.mp3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if mp3_files:
        logger.info("Downloaded (fallback): %s", mp3_files[0].name)
        return mp3_files[0]

    raise RuntimeError(
        "❌ Instagram fayl yuklab olinmadi.\n\n"
        "💡 Iltimos, videoni o'zingiz yuklab olib, "
        "menga ovozli xabar sifatida yuboring."
    )
