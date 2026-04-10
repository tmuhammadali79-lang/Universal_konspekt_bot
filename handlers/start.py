"""/start, /help, /mystats, /language, /mode, and settings handlers."""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from database.models import get_user, create_user, update_user_language, update_user_mode
from keyboards.reply import main_menu_keyboard
from keyboards.inline import language_keyboard, mode_keyboard
from services.limits import get_user_stats
from services.summarizer import MODE_LABELS
from utils.helpers import generate_referral_code

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_TEXT = """🤖 **Smart Summary AI** ga xush kelibsiz!

Men ovozli xabarlar, YouTube va Instagram videolarini matnga aylantirib, qisqa konspekt tayyorlayman.

📌 **Qanday ishlatiladi:**
1️⃣ Menga ovozli xabar yuboring
2️⃣ YouTube yoki Instagram Reels linkini tashlang
3️⃣ Men sizga avtomatik konspekt tayyorlayman!

🤖 **AI Rejimlari:**
📝 Standart — umumiy konspekt
🎓 Talaba — konspekt + test savollari
💼 Biznes — majlis bayonnomasi
🎬 Bloger — video uchun ssenariy

🆓 **Bepul rejada:** Kuniga 3 ta so'rov, 10 daqiqalik audio

Rejimni o'zgartirish: /mode
Boshlash uchun ovozli xabar yuboring yoki link tashlang! 👇"""

HELP_TEXT = """📚 **Yordam**

**Asosiy buyruqlar:**
/start — Botni qayta ishga tushirish
/help — Shu yordam sahifasi
/mode — AI rejimini o'zgartirish
/mystats — Statistikangiz
/history — Konspektlar tarixi
/premium — Premium ma'lumotlari
/language — Til sozlamalari

**AI Rejimlari:**
📝 **Standart** — umumiy konspekt
🎓 **Talaba** — ma'ruza konspekti + 5 ta test savoli (imtihonga tayyorlanish)
💼 **Biznes** — majlis bayonnomasi (kim nima dedi, topshiriqlar, muddatlar)
🎬 **Bloger** — Reels/TikTok uchun tayyor ssenariy (hook, body, CTA)

**Qanday ishlaydi:**
• Ovozli xabar → Matn + Konspekt
• Video xabar (kruglyash) → Matn + Konspekt
• YouTube link → Audio → Matn + Konspekt
• Instagram Reels link → Audio → Matn + Konspekt

**Limitlar (bepul):**
• Kuniga 3 ta so'rov
• Kuniga 10 daqiqalik audio
• Har bir referal uchun +5 daqiqa

💡 **Maxsus:** O'zbek shevalaridagi nutqni avtomatik adabiy tilga o'giramiz!"""


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Handle /start with optional referral deeplink."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        # Check for referral
        referred_by = None
        if message.text and "ref_" in message.text:
            parts = message.text.split()
            for part in parts:
                if part.startswith("ref_"):
                    ref_code = part.replace("ref_", "")
                    import aiosqlite
                    from config import DB_PATH
                    async with aiosqlite.connect(DB_PATH) as db:
                        cursor = await db.execute(
                            "SELECT user_id FROM users WHERE referral_code = ?",
                            (ref_code,),
                        )
                        row = await cursor.fetchone()
                        if row and row[0] != user_id:
                            referred_by = row[0]
                    break

        await create_user(
            user_id=user_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            referral_code=generate_referral_code(),
            referred_by=referred_by,
        )

        if referred_by:
            await message.answer("🎉 Referal orqali keldingiz! Bonuslar qo'shildi.")

    await message.answer(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "⚙️ Sozlamalar")
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("mystats"))
@router.message(F.text == "📊 Statistika")
async def cmd_stats(message: Message) -> None:
    if not message.from_user:
        return
    stats = await get_user_stats(message.from_user.id)
    await message.answer(stats, parse_mode="Markdown")


# ── AI Mode selection ────────────────────────────────

@router.message(Command("mode"))
@router.message(F.text == "🤖 AI Rejim")
async def cmd_mode(message: Message) -> None:
    """Show AI mode selection."""
    if not message.from_user:
        return

    user = await get_user(message.from_user.id)
    current_mode = user["ai_mode"] if user else "standard"
    mode_label = MODE_LABELS.get(current_mode, "📝 Standart")

    await message.answer(
        f"🤖 **AI Rejimini tanlang**\n\n"
        f"Hozirgi rejim: {mode_label}\n\n"
        f"📝 **Standart** — umumiy konspekt\n"
        f"🎓 **Talaba** — konspekt + 5 ta test savoli\n"
        f"💼 **Biznes** — majlis bayonnomasi\n"
        f"🎬 **Bloger** — Reels/TikTok ssenariy",
        parse_mode="Markdown",
        reply_markup=mode_keyboard(current_mode),
    )


@router.callback_query(F.data.startswith("set_mode:"))
async def cb_set_mode(callback: CallbackQuery) -> None:
    """Handle mode selection callback."""
    if not callback.data or not callback.from_user:
        return

    mode = callback.data.split(":")[1]
    if mode not in MODE_LABELS:
        await callback.answer("Noto'g'ri rejim.", show_alert=True)
        return

    await update_user_mode(callback.from_user.id, mode)
    mode_label = MODE_LABELS[mode]

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"\u2705 AI rejimi o'zgartirildi: {mode_label}\n\n"
            f"Endi ovozli xabar yuboring yoki link tashlang \u2014 "
            f"shu rejimda konspekt tayyorlanadi!",
            parse_mode="Markdown",
            reply_markup=mode_keyboard(mode),
        )
    except Exception:
        pass  # message already shows this mode
    await callback.answer(f"Rejim: {mode_label}")


# ── Language ─────────────────────────────────────────

@router.message(Command("language"))
async def cmd_language(message: Message) -> None:
    await message.answer(
        "🌐 Konspekt tilini tanlang:",
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def cb_set_language(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return
    lang = callback.data.split(":")[1]
    await update_user_language(callback.from_user.id, lang)
    lang_name = "Lotin" if lang == "lat" else "Кирилл"
    await callback.message.edit_text(f"✅ Til o'zgartirildi: {lang_name}")  # type: ignore[union-attr]


@router.callback_query(F.data == "my_stats")
async def cb_my_stats(callback: CallbackQuery) -> None:
    if not callback.from_user:
        return
    stats = await get_user_stats(callback.from_user.id)
    await callback.message.edit_text(stats, parse_mode="Markdown")  # type: ignore[union-attr]
