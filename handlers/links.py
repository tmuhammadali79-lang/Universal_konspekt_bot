"""YouTube and Instagram link handler."""

import logging

from aiogram import Router, F, Bot
from aiogram.types import Message

from config import TEMP_DIR
from database.models import get_user, log_usage, save_summary
from keyboards.inline import summary_keyboard
from services.limits import check_limit
from services.media_processor import convert_to_mp3, get_duration, cleanup
from services.transcriber import transcribe_audio
from services.summarizer import summarize_text
from services.youtube_dl import download_youtube_audio, get_youtube_info
from services.instagram_dl import download_instagram_audio
from utils.helpers import detect_url_type, truncate, format_duration

logger = logging.getLogger(__name__)
router = Router(name="links")


@router.message(F.text)
async def handle_text_links(message: Message, bot: Bot) -> None:
    """Detect YouTube/Instagram links and process them."""
    if not message.from_user or not message.text:
        return

    url_info = detect_url_type(message.text)
    if not url_info:
        return

    url_type, url = url_info
    user_id = message.from_user.id

    # ── 1. Check limits ──────────────────────────────
    limit = await check_limit(user_id)
    if not limit["allowed"]:
        await message.reply(limit["reason"])
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
        logger.exception("Link processing error for user %d: %s", user_id, url)
        try:
            await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)[:200]}")
        except Exception:
            pass  # status message may have been deleted
    finally:
        if audio_path:
            cleanup(audio_path)
        if mp3_path:
            cleanup(mp3_path)
