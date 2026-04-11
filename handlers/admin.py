"""Admin commands: stats, broadcast, premium grant, user block."""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS
from database.models import (
    get_total_users, get_total_summaries, get_all_user_ids,
    get_user, block_user, unblock_user,
    set_unlimited_premium, remove_premium,
    get_all_users,
)

logger = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── /admin — show all admin commands ─────────────────

@router.message(Command("admin"))
async def cmd_admin_help(message: Message) -> None:
    """Show admin help."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    await message.answer(
        "🔐 Admin buyruqlari:\n\n"
        "📊 /stats - bot statistikasi\n"
        "📢 /broadcast [matn] - barchaga xabar\n"
        "👥 /users - barcha foydalanuvchilar royxati\n\n"
        "⭐ /grant [user_id] - cheksiz premium berish\n"
        "❌ /revoke [user_id] - premiumni olib tashlash\n\n"
        "🚫 /block [user_id] - foydalanuvchini bloklash\n"
        "✅ /unblock [user_id] - blokdan chiqarish\n\n"
        "👤 /userinfo [user_id] - foydalanuvchi malumotlari",
    )


# ── /users — list all users ──────────────────────────

@router.message(Command("users"))
async def cmd_users_list(message: Message) -> None:
    """Admin: list all users with IDs."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    users = await get_all_users()
    if not users:
        await message.answer("👥 Hozircha foydalanuvchilar yo'q.")
        return

    # Build user list in chunks to avoid message length limits
    CHUNK_SIZE = 50
    for i in range(0, len(users), CHUNK_SIZE):
        chunk = users[i:i + CHUNK_SIZE]
        lines = []
        for idx, u in enumerate(chunk, start=i + 1):
            uid = u["user_id"]
            name = u.get("full_name") or "Nomalum"
            uname = f"@{u['username']}" if u.get("username") else "—"
            status = ""
            if u.get("is_premium"):
                status += "⭐"
            if u.get("is_blocked"):
                status += "🚫"
            lines.append(f"{idx}. {name} ({uname})\n   🆔 `{uid}` {status}")

        header = f"👥 Foydalanuvchilar ro'yhati ({len(users)} ta):\n\n"
        text = header + "\n\n".join(lines) if i == 0 else "\n\n".join(lines)
        await message.answer(text, parse_mode="Markdown")


# ── /stats ───────────────────────────────────────────

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


# ── /grant <user_id> — give unlimited premium ────────

@router.message(Command("grant"))
async def cmd_grant_premium(message: Message) -> None:
    """Admin: grant unlimited premium to a user."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Foydalanish: /grant [user\_id]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Notoqri user\_id. Raqam kiriting.")
        return

    user = await get_user(target_id)
    if not user:
        await message.answer(f"Foydalanuvchi topilmadi: {target_id}")
        return

    await set_unlimited_premium(target_id)
    name = user.get("full_name", "Nomalum")
    await message.answer(
        f"✅ **Cheksiz Premium berildi!**\n\n"
        f"👤 {name}\n"
        f"🆔 `{target_id}`",
        parse_mode="Markdown",
    )


# ── /revoke <user_id> — remove premium ───────────────

@router.message(Command("revoke"))
async def cmd_revoke_premium(message: Message) -> None:
    """Admin: remove premium from a user."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Foydalanish: /revoke [user\_id]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Notoqri user\_id.")
        return

    user = await get_user(target_id)
    if not user:
        await message.answer(f"Foydalanuvchi topilmadi: {target_id}")
        return

    await remove_premium(target_id)
    name = user.get("full_name", "Nomalum")
    await message.answer(
        f"✅ **Premium olib tashlandi**\n\n"
        f"👤 {name}\n"
        f"🆔 `{target_id}`",
        parse_mode="Markdown",
    )


# ── /block <user_id> — block user ────────────────────

@router.message(Command("block"))
async def cmd_block_user(message: Message) -> None:
    """Admin: block a user."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Foydalanish: /block [user\_id]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Notoqri user\_id.")
        return

    # Prevent blocking admins
    if target_id in ADMIN_IDS:
        await message.answer("❌ Admin foydalanuvchini bloklash mumkin emas!")
        return

    user = await get_user(target_id)
    if not user:
        await message.answer(f"Foydalanuvchi topilmadi: {target_id}")
        return

    await block_user(target_id)
    name = user.get("full_name", "Nomalum")
    await message.answer(
        f"🚫 **Foydalanuvchi bloklandi!**\n\n"
        f"👤 {name}\n"
        f"🆔 `{target_id}`",
        parse_mode="Markdown",
    )


# ── /unblock <user_id> — unblock user ────────────────

@router.message(Command("unblock"))
async def cmd_unblock_user(message: Message) -> None:
    """Admin: unblock a user."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Foydalanish: /unblock [user\_id]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Notoqri user\_id.")
        return

    user = await get_user(target_id)
    if not user:
        await message.answer(f"Foydalanuvchi topilmadi: {target_id}")
        return

    await unblock_user(target_id)
    name = user.get("full_name", "Nomalum")
    await message.answer(
        f"✅ **Blokdan chiqarildi!**\n\n"
        f"👤 {name}\n"
        f"🆔 `{target_id}`",
        parse_mode="Markdown",
    )


# ── /userinfo <user_id> — user details ───────────────

@router.message(Command("userinfo"))
async def cmd_user_info(message: Message) -> None:
    """Admin: show user details."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    if not message.text:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Foydalanish: /userinfo [user\_id]")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Notoqri user\_id.")
        return

    user = await get_user(target_id)
    if not user:
        await message.answer(f"Foydalanuvchi topilmadi: {target_id}")
        return

    premium_status = "Yoq"
    if user.get("is_premium"):
        until = user.get("premium_until", "")
        premium_status = f"Ha ({until})" if until else "Ha"

    blocked_status = "Ha" if user.get("is_blocked") else "Yoq"

    uid = user['user_id']
    name = user.get('full_name', 'Nomalum')
    uname = user.get('username', 'yoq')
    ai_mode = user.get('ai_mode', 'standard')
    ref_code = user.get('referral_code', '')
    created = user.get('created_at', '')

    await message.answer(
        f"👤 Foydalanuvchi malumotlari\n\n"
        f"🆔 ID: {uid}\n"
        f"📛 Ism: {name}\n"
        f"👤 Username: @{uname}\n"
        f"🤖 AI rejim: {ai_mode}\n"
        f"⭐ Premium: {premium_status}\n"
        f"🚫 Bloklangan: {blocked_status}\n"
        f"🔗 Referal kod: {ref_code}\n"
        f"📅 Royxatdan otgan: {created}",
    )


# ── /broadcast ───────────────────────────────────────

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

        # Rate limit: avoid Telegram FloodWait (max ~30 msg/sec)
        await asyncio.sleep(0.05)

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
