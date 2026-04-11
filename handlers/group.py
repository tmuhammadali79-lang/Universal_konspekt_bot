"""Group auto-summary handler — Viral Loop feature.

When the bot is added to a group, it automatically listens for long voice
messages and replies with a compact text summary underneath.
This gives massive visibility to the bot in group chats.
"""

import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER

from config import TEMP_DIR, GROUP_VOICE_MIN_DURATION
from services.media_processor import convert_to_mp3, get_duration, cleanup
from services.transcriber import transcribe_audio
from services.summarizer import summarize_text
from utils.helpers import truncate

logger = logging.getLogger(__name__)
router = Router(name="group")


# ── Bot added to group ───────────────────────────────

@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated, bot: Bot) -> None:
    """Send welcome message when bot is added to a group."""
    # BUG FIX: ChatMemberUpdated has no .answer() — use bot.send_message
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "FAHM_AI_BOT"

    await bot.send_message(
        chat_id=event.chat.id,
        text=(
            f"👋 **Smart Summary AI** guruhga qo'shildi!\n\n"
            f"Men {GROUP_VOICE_MIN_DURATION} soniyadan uzun ovozli xabarlarni "
            f"avtomatik matnga aylantirib, qisqa konspekt tayyorlayman.\n\n"
            f"💡 Shaxsiy foydalanish uchun: @{bot_username}"
        ),
        parse_mode="Markdown",
    )


# ── Auto-summarize long voice messages in groups ─────

@router.message(F.voice, F.chat.type.in_({"group", "supergroup"}))
async def handle_group_voice(message: Message, bot: Bot) -> None:
    """Auto-summarize voice messages longer than threshold in groups."""
    if not message.voice or not message.from_user:
        return

    # Only process voice messages longer than the threshold
    voice_duration = message.voice.duration or 0
    if voice_duration < GROUP_VOICE_MIN_DURATION:
        return

    logger.info(
        "Group voice: chat=%s, user=%s, duration=%ds",
        message.chat.id, message.from_user.id, voice_duration,
    )

    raw_path = None
    mp3_path = None
    try:
        # Download
        file = await bot.get_file(message.voice.file_id)
        raw_path = TEMP_DIR / f"grp_{message.chat.id}_{file.file_id}.ogg"
        await bot.download_file(file.file_path, raw_path)  # type: ignore[arg-type]

        # Convert
        mp3_path = await convert_to_mp3(raw_path, f"grp_{message.chat.id}_{file.file_id}.mp3")
        duration = await get_duration(mp3_path)

        # Transcribe (with dialect normalization)
        transcript = await transcribe_audio(mp3_path)

        if not transcript.strip():
            return  # Silently skip — don't spam the group

        # Summarize (standard mode for groups)
        result = await summarize_text(transcript, duration, mode="standard")

        # Get bot username dynamically
        bot_info = await bot.get_me()
        bot_username = bot_info.username or "FAHM_AI_BOT"

        # Format group-friendly compact message
        sender_name = message.from_user.full_name or "Foydalanuvchi"
        group_text = (
            f"📝 **Ovozli xabar konspekti**\n"
            f"👤 _{sender_name}_\n\n"
            f"{truncate(result['summary'], 3500)}\n\n"
            f"🤖 _@{bot_username} — shaxsiy foydalanish uchun botga o'ting!_"
        )

        await message.reply(group_text, parse_mode="Markdown")

    except Exception as e:
        logger.warning("Group voice processing error: %s", e)
        # Don't send error messages in groups — too spammy
    finally:
        if raw_path:
            cleanup(raw_path)
        if mp3_path:
            cleanup(mp3_path)
