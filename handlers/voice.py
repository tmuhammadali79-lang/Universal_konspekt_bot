"""Voice message and video note (kruglyash) handler."""

import asyncio
import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message

from config import TEMP_DIR
from database.models import get_user, log_usage, save_summary
from keyboards.inline import summary_keyboard, limit_keyboard
from services.limits import check_limit
from services.media_processor import convert_to_mp3, get_duration, cleanup
from services.transcriber import transcribe_audio
from services.summarizer import summarize_text
from utils.helpers import truncate

logger = logging.getLogger(__name__)
router = Router(name="voice")

# Max retries for downloading from Telegram
DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT = 60  # seconds


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot) -> None:
    """Process voice messages."""
    if not message.from_user or not message.voice:
        return
    await _process_audio(message, bot, media_type="voice")


@router.message(F.video_note)
async def handle_video_note(message: Message, bot: Bot) -> None:
    """Process video notes (kruglyash)."""
    if not message.from_user or not message.video_note:
        return
    await _process_audio(message, bot, media_type="video_note")


async def _download_with_retry(bot: Bot, file_path: str, dest: Path) -> None:
    """Download file from Telegram with retries and timeout."""
    last_error = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            await asyncio.wait_for(
                bot.download_file(file_path, dest),
                timeout=DOWNLOAD_TIMEOUT,
            )
            return  # success
        except (asyncio.TimeoutError, TimeoutError, Exception) as e:
            last_error = e
            logger.warning(
                "Download attempt %d/%d failed: %s",
                attempt, DOWNLOAD_RETRIES, type(e).__name__,
            )
            if attempt < DOWNLOAD_RETRIES:
                await asyncio.sleep(2)
    raise RuntimeError(
        f"Faylni yuklab olishda xatolik ({DOWNLOAD_RETRIES} urinishdan keyin). "
        "Internet ulanishingizni tekshiring."
    )


async def _process_audio(message: Message, bot: Bot, media_type: str) -> None:
    """Common pipeline: download -> convert -> transcribe -> summarize."""
    user_id = message.from_user.id  # type: ignore[union-attr]

    # -- 1. Check limits ---
    limit = await check_limit(user_id)
    if not limit["allowed"]:
        await message.reply(
            limit["reason"],
            reply_markup=limit_keyboard(),
        )
        return

    # -- 2. Get user AI mode ---
    user = await get_user(user_id)
    ai_mode = user["ai_mode"] if user else "standard"

    # -- 3. Progress message ---
    status_msg = await message.reply("Qayta ishlanmoqda... Iltimos, kuting.")

    file = None
    raw_path = None
    mp3_path = None
    try:
        # -- 4. Download file from Telegram ---
        if media_type == "voice":
            file = await bot.get_file(message.voice.file_id)  # type: ignore[union-attr]
        else:
            file = await bot.get_file(message.video_note.file_id)  # type: ignore[union-attr]

        raw_path = TEMP_DIR / f"{user_id}_{file.file_id}.ogg"
        await _download_with_retry(bot, file.file_path, raw_path)  # type: ignore[arg-type]

        try:
            await status_msg.edit_text("Audio konvertatsiya qilinmoqda...")
        except Exception:
            pass

        # -- 5. Convert to MP3 ---
        mp3_path = await convert_to_mp3(raw_path, f"{user_id}_{file.file_id}.mp3")
        duration = await get_duration(mp3_path)

        try:
            await status_msg.edit_text("Matn tanib olinmoqda (Whisper AI)...")
        except Exception:
            pass

        # -- 6. Transcribe (with dialect normalization) ---
        transcript = await transcribe_audio(mp3_path)

        if not transcript.strip():
            try:
                await status_msg.edit_text("Audio dan matn aniqlanmadi. Iltimos, aniqroq gapiring.")
            except Exception:
                pass
            return

        try:
            await status_msg.edit_text("Konspekt tayyorlanmoqda (AI)...")
        except Exception:
            pass

        # -- 7. Summarize (with AI mode) ---
        result = await summarize_text(transcript, duration, mode=ai_mode)

        # -- 8. Save to DB ---
        summary_id = await save_summary(
            user_id=user_id,
            topic=result["topic"],
            summary_text=result["summary"],
            full_text=transcript,
            media_type=media_type,
            duration=duration,
        )
        await log_usage(user_id, media_type, duration)

        # -- 9. Send result ---
        try:
            await status_msg.edit_text(
                truncate(result["summary"]),
                parse_mode="Markdown",
                reply_markup=summary_keyboard(summary_id),
            )
        except Exception:
            # If Markdown fails, send without formatting
            try:
                await status_msg.edit_text(
                    truncate(result["summary"]),
                    reply_markup=summary_keyboard(summary_id),
                )
            except Exception:
                pass

    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        logger.exception("Voice processing error for user %d", user_id)
        try:
            await status_msg.edit_text(
                f"Xatolik yuz berdi: {error_msg[:200]}"
            )
        except Exception:
            pass  # status message may have been deleted
    finally:
        if raw_path:
            cleanup(raw_path)
        if mp3_path:
            cleanup(mp3_path)
