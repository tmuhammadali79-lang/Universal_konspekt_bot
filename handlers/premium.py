"""Premium and referral handler."""

import logging
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

from config import PREMIUM_STARS_PRICE
from database.models import get_user, set_premium
from keyboards.inline import premium_keyboard

logger = logging.getLogger(__name__)
router = Router(name="premium")


PREMIUM_TEXT = """⭐ **Smart Summary AI Premium**

🆓 **Bepul reja:**
• Kuniga {free_req} ta so'rov
• Kuniga {free_min} daqiqalik audio
• Referal bonus: har bir do'st uchun +{ref_bonus} daqiqa

⭐ **Premium reja ({stars_price} Stars/oy):**
• ♾ Cheksiz so'rovlar
• ♾ Cheksiz audio
• 📂 Katta fayl hajmi
• 🚀 Ustuvor navbat

👥 **Sizning referallaringiz:** {ref_count} ta
🔗 **Referal kodingiz:** `{ref_code}`"""


@router.message(Command("premium"))
@router.message(F.text == "⭐ Premium")
async def cmd_premium(message: Message, bot: Bot) -> None:
    """Show premium info and referral link."""
    if not message.from_user:
        return

    from config import FREE_DAILY_REQUESTS, FREE_DAILY_MINUTES, REFERRAL_BONUS_MINUTES
    from database.models import get_referral_count

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Iltimos, avval /start buyrug'ini yuboring.")
        return

    ref_count = await get_referral_count(message.from_user.id)
    bot_info = await bot.get_me()

    text = PREMIUM_TEXT.format(
        free_req=FREE_DAILY_REQUESTS,
        free_min=FREE_DAILY_MINUTES,
        ref_bonus=REFERRAL_BONUS_MINUTES,
        stars_price=PREMIUM_STARS_PRICE,
        ref_count=ref_count,
        ref_code=user["referral_code"],
    )

    if user["is_premium"]:
        if user["premium_until"]:
            until = datetime.fromisoformat(user["premium_until"])
            if until > datetime.utcnow():
                text += f"\n\n✅ Siz Premium foydalanuvchisiz!"
                text += f"\n📅 Amal qilish muddati: {user['premium_until'][:10]}"
            else:
                text += "\n\n⏰ Premium muddati tugagan. Yangilang!"
        else:
            text += f"\n\n✅ Siz Premium foydalanuvchisiz!"

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=premium_keyboard(bot_info.username or "", user["referral_code"]),
    )


# BUG FIX: Removed the hacky msg.from_user reassignment.
# Instead, just call cmd_premium properly with the callback context.
@router.callback_query(F.data == "premium_info")
async def cb_premium_info(callback: CallbackQuery, bot: Bot) -> None:
    """Show premium info via callback."""
    if not callback.from_user:
        return

    from config import FREE_DAILY_REQUESTS, FREE_DAILY_MINUTES, REFERRAL_BONUS_MINUTES
    from database.models import get_referral_count

    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Iltimos, avval /start buyrug'ini yuboring.", show_alert=True)
        return

    ref_count = await get_referral_count(callback.from_user.id)
    bot_info = await bot.get_me()

    text = PREMIUM_TEXT.format(
        free_req=FREE_DAILY_REQUESTS,
        free_min=FREE_DAILY_MINUTES,
        ref_bonus=REFERRAL_BONUS_MINUTES,
        stars_price=PREMIUM_STARS_PRICE,
        ref_count=ref_count,
        ref_code=user["referral_code"],
    )

    if user["is_premium"]:
        if user["premium_until"]:
            until = datetime.fromisoformat(user["premium_until"])
            if until > datetime.utcnow():
                text += f"\n\n✅ Siz Premium foydalanuvchisiz!"
                text += f"\n📅 Amal qilish muddati: {user['premium_until'][:10]}"
            else:
                text += "\n\n⏰ Premium muddati tugagan. Yangilang!"

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        parse_mode="Markdown",
        reply_markup=premium_keyboard(bot_info.username or "", user["referral_code"]),
    )
    await callback.answer()


@router.callback_query(F.data == "buy_premium")
async def cb_buy_premium(callback: CallbackQuery, bot: Bot) -> None:
    """Initiate Telegram Stars payment."""
    if not callback.from_user or not callback.message:
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Smart Summary AI Premium",
        description="1 oylik premium obuna -- cheksiz konspektlar!",
        payload=f"premium_{callback.from_user.id}",
        provider_token="",   # empty for Telegram Stars
        currency="XTR",      # Telegram Stars
        prices=[LabeledPrice(label="Premium (1 oy)", amount=PREMIUM_STARS_PRICE)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Approve the payment."""
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    """Handle successful payment — activate premium."""
    if not message.from_user or not message.successful_payment:
        return

    user_id = message.from_user.id
    until = (datetime.utcnow() + timedelta(days=30)).isoformat()

    await set_premium(user_id, until)

    await message.answer(
        "🎉 **Tabriklaymiz!**\n\n"
        "⭐ Premium muvaffaqiyatli faollashtirildi!\n"
        "📅 Amal qilish muddati: 30 kun\n\n"
        "Endi cheksiz konspekt yaratishingiz mumkin! 🚀",
        parse_mode="Markdown",
    )
