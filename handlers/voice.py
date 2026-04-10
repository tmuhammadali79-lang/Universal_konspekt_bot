"""Voice message and video note (kruglyash) handler."""

import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message

from config import TEMP_DIR
from database.models import get_user, log_usage, save_summary
from keyboards.inline import summary_keyboard
from services.limits import check_limit
from services.media_processor import convert_to_mp3, get_duration, cleanup
from services.transcriber import transcribe_audio
from services.summarizer import summarize_text
from utils.helpers import truncate

logger = logging.getLogger(__name__)
router = Router(name="voice")


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


async def _process_audio(message: Message, bot: Bot, media_type: str) -> None:
    """Common pipeline: download → convert → transcribe → summarize."""
    user_id = message.from_user.id  # type: ignore[union-attr]

    # ── 1. Check limits ──────────────────────────────
    limit = await check_limit(user_id)
    if not limit["allowed"]:
        await message.reply(limit["reason"])
        return

    # ── 2. Get user AI mode ──────────────────────────
    user = await get_user(user_id)
    ai_mode = user["ai_mode"] if user else "standard"

    # ── 3. Progress message ──────────────────────────
    status_msg = await message.reply("⏳ Qayta ishlanmoqda... Iltimos, kuting.")

    file = None
    try:
        # ── 4. Download file from Telegram ───────────
        if media_type == "voice":
            file = await bot.get_file(message.voice.file_id)  # type: ignore[union-attr]
        else:
            file = await bot.get_file(message.video_note.file_id)  # type: ignore[union-attr]

        raw_path = TEMP_DIR / f"{user_id}_{file.file_id}.ogg"
        await bot.download_file(file.file_path, raw_path)  # type: ignore[arg-type]

        await status_msg.edit_text("🔄 Audio konvertatsiya qilinmoqda...")

        # ── 5. Convert to MP3 ────────────────────────
        mp3_path = await convert_to_mp3(raw_path, f"{user_id}_{file.file_id}.mp3")
        duration = await get_duration(mp3_path)

        await status_msg.edit_text("🎙 Matn tanib olinmoqda (Whisper AI)...")

        # ── 6. Transcribe (with dialect normalization) ──
        transcript = await transcribe_audio(mp3_path)

        if not transcript.strip():
            await status_msg.edit_text("⚠️ Audio dan matn aniqlanmadi. Iltimos, aniqroq gapiring.")
            cleanup(raw_path, mp3_path)
            return

        await status_msg.edit_text("🧠 Konspekt tayyorlanmoqda (AI)...")

        # ── 7. Summarize (with AI mode) ──────────────
        result = await summarize_text(transcript, duration, mode=ai_mode)

        # ── 8. Save to DB ────────────────────────────
        summary_id = await save_summary(
            user_id=user_id,
            topic=result["topic"],
            summary_text=result["summary"],
            full_text=transcript,
            media_type=media_type,
            duration=duration,
        )
        await log_usage(user_id, media_type, duration)

        # ── 9. Send result ───────────────────────────
        await status_msg.edit_text(
            truncate(result["summary"]),
            parse_mode="Markdown",
            reply_markup=summary_keyboard(summary_id),
        )

    except Exception as e:
        logger.exception("Voice processing error for user %d", user_id)
        try:
            await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)[:200]}")
        except Exception:
            pass  # status message may have been deleted
    finally:
        if file:
            cleanup(
                TEMP_DIR / f"{user_id}_{file.file_id}.ogg",
                TEMP_DIR / f"{user_id}_{file.file_id}.mp3",
            )
