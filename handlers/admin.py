"""Admin commands: stats, broadcast."""

import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS
from database.models import get_total_users, get_total_summaries, get_all_user_ids

logger = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("stats"))
async def cmd_admin_stats(message: Message) -> None:
    """Admin: show bot statistics."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    total_users = await get_total_users()
    total_summaries = await get_total_summaries()

    await message.answer(
        f"📊 **Admin Statistika**\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"📝 Jami konspektlar: {total_summaries}",
        parse_mode="Markdown",
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    """Admin: broadcast message to all users.

    Usage: /broadcast Your message here
    """
    if not message.from_user or not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("Foydalanish: /broadcast <xabar matni>")
        return

    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0

    status = await message.answer(f"📤 Xabar yuborilmoqda... (0/{len(user_ids)})")

    for uid in user_ids:
        try:
            await bot.send_message(uid, f"📢 **E'lon:**\n\n{text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

        if (sent + failed) % 50 == 0:
            try:
                await status.edit_text(f"📤 Yuborilmoqda... ({sent + failed}/{len(user_ids)})")
            except Exception:
                pass

    await status.edit_text(
        f"✅ **Broadcast yakunlandi**\n\n"
        f"📤 Yuborildi: {sent}\n"
        f"❌ Xato: {failed}\n"
        f"👥 Jami: {len(user_ids)}",
        parse_mode="Markdown",
    )
