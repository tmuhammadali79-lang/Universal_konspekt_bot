"""FFmpeg wrapper — converts audio/video to low-bitrate MP3 for Whisper."""

import asyncio
import os
import logging
from pathlib import Path
from config import TEMP_DIR

logger = logging.getLogger(__name__)


async def convert_to_mp3(input_path: str | Path, output_name: str | None = None) -> Path:
    """Convert any audio/video file to 64kbps mono MP3.

    Returns the path to the resulting MP3 file in TEMP_DIR.
    """
    input_path = Path(input_path)
    if output_name is None:
        output_name = input_path.stem + ".mp3"
    output_path = TEMP_DIR / output_name

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vn",                   # no video
        "-acodec", "libmp3lame",
        "-ab", "64k",           # low bitrate to save resources
        "-ar", "16000",         # 16kHz — optimal for Whisper
        "-ac", "1",             # mono
        str(output_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error("FFmpeg error: %s", stderr.decode(errors="replace"))
        raise RuntimeError(f"FFmpeg conversion failed (code {process.returncode})")

    return output_path


async def get_duration(file_path: str | Path) -> int:
    """Get audio/video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    try:
        return int(float(stdout.decode().strip()))
    except (ValueError, AttributeError):
        return 0


async def split_audio(file_path: Path, chunk_seconds: int = 600) -> list[Path]:
    """Split a long audio file into chunks of `chunk_seconds`.

    Returns list of chunk file paths.
    """
    duration = await get_duration(file_path)
    if duration <= chunk_seconds:
        return [file_path]

    chunks: list[Path] = []
    start = 0
    idx = 0
    while start < duration:
        chunk_path = TEMP_DIR / f"{file_path.stem}_chunk{idx}.mp3"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(file_path),
            "-ss", str(start),
            "-t", str(chunk_seconds),
            "-acodec", "libmp3lame",
            "-ab", "64k", "-ar", "16000", "-ac", "1",
            str(chunk_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        if chunk_path.exists():
            chunks.append(chunk_path)
        start += chunk_seconds
        idx += 1

    return chunks


def cleanup(*paths: str | Path) -> None:
    """Remove temporary files."""
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass
