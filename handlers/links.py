"""YouTube, Instagram link handler AND plain text summarization."""

import logging

from aiogram import Router, F, Bot
from aiogram.types import Message

from config import TEMP_DIR
from database.models import get_user, log_usage, save_summary
from keyboards.inline import summary_keyboard, limit_keyboard
from services.limits import check_limit
from services.media_processor import convert_to_mp3, get_duration, cleanup
from services.transcriber import transcribe_audio
from services.summarizer import summarize_text
from services.youtube_dl import download_youtube_audio, get_youtube_info
from services.instagram_dl import download_instagram_audio
from utils.helpers import detect_url_type, truncate, format_duration

logger = logging.getLogger(__name__)
router = Router(name="links")

# Minimum text length to summarize (too short = not worth it)
MIN_TEXT_LENGTH = 50


@router.message(F.text)
async def handle_text_links(message: Message, bot: Bot) -> None:
    """Detect YouTube/Instagram links OR plain text and process them."""
    if not message.from_user or not message.text:
        return

    text = message.text.strip()

    # Skip commands (start with /)
    if text.startswith("/"):
        return

    # Skip menu button texts (handled by start.py)
    menu_buttons = {"⚙️ Sozlamalar", "📊 Statistika", "📜 Tarix", "⭐ Premium", "🤖 AI Rejim"}
    if text in menu_buttons:
        return

    # Check if it's a URL
    url_info = detect_url_type(text)

    if url_info:
        # ── URL mode: download and summarize ─────────
        await _handle_url(message, bot, url_info)
    else:
        # ── Text mode: summarize the text directly ───
        await _handle_plain_text(message)


async def _handle_plain_text(message: Message) -> None:
    """Summarize plain text using the user's selected AI mode."""
    user_id = message.from_user.id  # type: ignore[union-attr]
    text = message.text.strip()  # type: ignore[union-attr]

    # Too short to summarize
    if len(text) < MIN_TEXT_LENGTH:
        await message.reply(
            f"⚠️ Matn juda qisqa (kamida {MIN_TEXT_LENGTH} ta belgi kerak).\n\n"
            "💡 Menga uzunroq matn, ovozli xabar yoki YouTube/Instagram link yuboring."
        )
        return

    # ── 1. Check limits ──────────────────────────────
    limit = await check_limit(user_id)
    if not limit["allowed"]:
        await message.reply(
            limit["reason"],
            reply_markup=limit_keyboard(),
        )
        return

    # ── 2. Get user AI mode ──────────────────────────
    user = await get_user(user_id)
    ai_mode = user["ai_mode"] if user else "standard"

    # ── 3. Progress message ──────────────────────────
    status_msg = await message.reply("🧠 Matn tahlil qilinmoqda...")

    try:
        # ── 4. Summarize ─────────────────────────────
        result = await summarize_text(text, duration_seconds=0, mode=ai_mode)

        # ── 5. Save to DB ────────────────────────────
        summary_id = await save_summary(
            user_id=user_id,
            topic=result["topic"],
            summary_text=result["summary"],
            full_text=text,
            media_type="text",
            duration=0,
        )
        await log_usage(user_id, "text", 0)

        # ── 6. Send result ───────────────────────────
        await status_msg.edit_text(
            truncate(result["summary"]),
            parse_mode="Markdown",
            reply_markup=summary_keyboard(summary_id),
        )

    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        logger.exception("Text processing error for user %d", user_id)
        try:
            await status_msg.edit_text(f"Xatolik yuz berdi: {error_msg[:200]}")
        except Exception:
            pass


async def _handle_url(message: Message, bot: Bot, url_info: tuple) -> None:
    """Download audio from URL and summarize."""
    url_type, url = url_info
    user_id = message.from_user.id  # type: ignore[union-attr]

    # ── 1. Check limits ──────────────────────────────
    limit = await check_limit(user_id)
    if not limit["allowed"]:
        await message.reply(
            limit["reason"],
            reply_markup=limit_keyboard(),
        )
        return

    # ── 2. Get user AI mode ──────────────────────────
    user = await get_user(user_id)
    ai_mode = user["ai_mode"] if user else "standard"

    status_msg = await message.reply(
        f"⏳ {'YouTube' if url_type == 'youtube' else 'Instagram'} dan audio yuklanmoqda..."
    )

    audio_path = None
    mp3_path = None

    try:
        # ── 3. Get video info (YouTube only) ─────────
        if url_type == "youtube":
            try:
                info = await get_youtube_info(url)
                video_title = info["title"]
                est_duration = info["duration"]
                if est_duration:
                    await status_msg.edit_text(
                        f"📹 **{video_title}**\n"
                        f"⏱ Davomiylik: {format_duration(est_duration)}\n\n"
                        f"⏳ Audio yuklanmoqda...",
                        parse_mode="Markdown",
                    )
            except Exception:
                pass

        # ── 4. Download audio ────────────────────────
        if url_type == "youtube":
            audio_path = await download_youtube_audio(url)
        else:
            audio_path = await download_instagram_audio(url)

        await status_msg.edit_text("🔄 Audio konvertatsiya qilinmoqda...")

        # ── 5. Convert to MP3 ────────────────────────
        mp3_path = await convert_to_mp3(audio_path, f"{user_id}_{url_type}.mp3")
        duration = await get_duration(mp3_path)

        await status_msg.edit_text("🎙 Matn tanib olinmoqda (Whisper AI)...")

        # ── 6. Transcribe (with dialect normalization) ──
        transcript = await transcribe_audio(mp3_path)

        if not transcript.strip():
            await status_msg.edit_text(
                "⚠️ Videoda nutq aniqlanmadi. Faqat musiqa yoki shovqin bo'lishi mumkin."
            )
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
            media_type=url_type,
            duration=duration,
        )
        await log_usage(user_id, url_type, duration)

        # ── 9. Send result ───────────────────────────
        await status_msg.edit_text(
            truncate(result["summary"]),
            parse_mode="Markdown",
            reply_markup=summary_keyboard(summary_id),
        )

    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        logger.exception("Link processing error for user %d: %s", user_id, url)
        try:
            await status_msg.edit_text(f"Xatolik yuz berdi: {error_msg[:200]}")
        except Exception:
            pass
    finally:
        if audio_path:
            cleanup(audio_path)
        if mp3_path:
            cleanup(mp3_path)
