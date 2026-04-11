"""History handler — view past summaries."""

import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database.models import get_user_summaries, get_summary_by_id
from keyboards.inline import history_keyboard
from utils.helpers import truncate

logger = logging.getLogger(__name__)
router = Router(name="history")


@router.message(Command("history"))
@router.message(F.text == "📜 Tarix")
async def cmd_history(message: Message) -> None:
    """Show paginated summary history."""
    if not message.from_user:
        return

    summaries = await get_user_summaries(message.from_user.id, limit=10, offset=0)

    if not summaries:
        await message.answer("📭 Hali konspektlar yo'q.\n\nMenga ovozli xabar yuboring yoki link tashlang!")
        return

    await message.answer(
        "📜 **Sizning konspektlaringiz:**",
        parse_mode="Markdown",
        reply_markup=history_keyboard(summaries, page=0),
    )


@router.callback_query(F.data.startswith("history_page:"))
async def cb_history_page(callback: CallbackQuery) -> None:
    """Navigate history pages."""
    if not callback.data or not callback.from_user:
        return

    page = int(callback.data.split(":")[1])
    offset = page * 10

    summaries = await get_user_summaries(callback.from_user.id, limit=10, offset=offset)

    if not summaries:
        await callback.answer("Boshqa konspektlar yo'q.", show_alert=True)
        return

    await callback.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=history_keyboard(summaries, page=page),
    )


@router.callback_query(F.data.startswith("view_summary:"))
async def cb_view_summary(callback: CallbackQuery) -> None:
    """View a specific summary."""
    if not callback.data:
        return

    summary_id = int(callback.data.split(":")[1])
    summary = await get_summary_by_id(summary_id)

    if not summary:
        await callback.answer("Konspekt topilmadi.", show_alert=True)
        return

    text = truncate(summary["summary_text"])
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            parse_mode="Markdown",
        )
    except Exception:
        # Markdown parse failed — send without formatting
        try:
            await callback.message.edit_text(text)  # type: ignore[union-attr]
        except Exception:
            pass


@router.callback_query(F.data.startswith("full_text:"))
async def cb_full_text(callback: CallbackQuery, bot: Bot) -> None:
    """View full transcript text."""
    if not callback.data or not callback.from_user:
        return

    summary_id = int(callback.data.split(":")[1])
    summary = await get_summary_by_id(summary_id)

    if not summary:
        await callback.answer("Konspekt topilmadi.", show_alert=True)
        return

    full_text = summary.get("full_text", "")
    if not full_text:
        await callback.answer("To'liq matn mavjud emas.", show_alert=True)
        return

    # BUG FIX: For long text, send as new messages using bot.send_message
    # instead of callback.message.answer() which can fail
    text = f"📄 **To'liq matn:**\n\n{full_text}"
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, chunk in enumerate(chunks):
            if i == 0:
                await callback.message.edit_text(chunk)  # type: ignore[union-attr]
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text=chunk,
                )
    else:
        await callback.message.edit_text(text)  # type: ignore[union-attr]
