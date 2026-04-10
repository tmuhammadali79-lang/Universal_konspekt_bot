import logging
from datetime import datetime

from config import FREE_DAILY_REQUESTS, FREE_DAILY_MINUTES, REFERRAL_BONUS_MINUTES
from database.models import get_user, get_today_usage, get_referral_count

logger = logging.getLogger(__name__)


async def check_limit(user_id: int) -> dict:
    """Check if user can make a request.

    Returns:
        dict with keys:
            - allowed (bool)
            - reason (str) — human-readable reason if not allowed
            - remaining_requests (int)
            - remaining_minutes (float)
    """
    user = await get_user(user_id)
    if not user:
        return {"allowed": False, "reason": "Foydalanuvchi topilmadi.", "remaining_requests": 0, "remaining_minutes": 0}

    # Blocked users — reject immediately
    if user.get("is_blocked"):
        return {
            "allowed": False,
            "reason": "🚫 Siz bloklangansiz. Admin bilan bog'laning.",
            "remaining_requests": 0,
            "remaining_minutes": 0,
        }

    # Premium users — unlimited
    if user["is_premium"]:
        # Unlimited premium (granted by admin)
        if user["premium_until"] == "unlimited":
            return {"allowed": True, "reason": "", "remaining_requests": 999, "remaining_minutes": 999}
        # Check if premium hasn't expired
        if user["premium_until"]:
            until = datetime.fromisoformat(user["premium_until"])
            if until > datetime.utcnow():
                return {"allowed": True, "reason": "", "remaining_requests": 999, "remaining_minutes": 999}
        # Premium expired → fall through to free tier

    # Free tier limits
    usage = await get_today_usage(user_id)
    referral_count = await get_referral_count(user_id)

    # Calculate bonus minutes from referrals
    bonus_minutes = referral_count * REFERRAL_BONUS_MINUTES
    total_allowed_minutes = FREE_DAILY_MINUTES + bonus_minutes
    total_allowed_seconds = total_allowed_minutes * 60

    remaining_requests = FREE_DAILY_REQUESTS - usage["count"]
    remaining_seconds = total_allowed_seconds - usage["seconds"]
    remaining_minutes = remaining_seconds / 60

    if remaining_requests <= 0:
        return {
            "allowed": False,
            "reason": (
                f"⚠️ Kunlik limit tugadi!\n"
                f"Siz bugun {FREE_DAILY_REQUESTS} ta so'rov ishlatdingiz.\n\n"
                f"💡 Ko'proq ishlatish uchun:\n"
                f"• Do'stlaringizni taklif qiling (+{REFERRAL_BONUS_MINUTES} daqiqa)\n"
                f"• /premium — cheksiz foydalanish"
            ),
            "remaining_requests": 0,
            "remaining_minutes": max(0, remaining_minutes),
        }

    if remaining_seconds <= 0:
        return {
            "allowed": False,
            "reason": (
                f"⚠️ Kunlik audio limiti tugadi!\n"
                f"Siz bugun {total_allowed_minutes} daqiqalik audio ishlatdingiz.\n\n"
                f"💡 Ko'proq ishlatish uchun:\n"
                f"• Do'stlaringizni taklif qiling (+{REFERRAL_BONUS_MINUTES} daqiqa)\n"
                f"• /premium — cheksiz foydalanish"
            ),
            "remaining_requests": remaining_requests,
            "remaining_minutes": 0,
        }

    return {
        "allowed": True,
        "reason": "",
        "remaining_requests": remaining_requests,
        "remaining_minutes": round(remaining_minutes, 1),
    }


async def get_user_stats(user_id: int) -> str:
    """Format user's current usage stats."""
    user = await get_user(user_id)
    if not user:
        return "Foydalanuvchi topilmadi."

    usage = await get_today_usage(user_id)
    referral_count = await get_referral_count(user_id)
    bonus = referral_count * REFERRAL_BONUS_MINUTES

    if user["is_premium"]:
        status = "⭐ Premium"
        if user["premium_until"]:
            status += f" (gacha: {user['premium_until'][:10]})"
    else:
        status = "🆓 Bepul"

    total_minutes = FREE_DAILY_MINUTES + bonus
    used_minutes = round(usage["seconds"] / 60, 1)

    from services.summarizer import MODE_LABELS
    ai_mode = MODE_LABELS.get(user.get("ai_mode", "standard"), "📝 Standart")

    return (
        f"📊 **Sizning statistikangiz**\n\n"
        f"👤 Status: {status}\n"
        f"🤖 AI Rejim: {ai_mode}\n"
        f"📅 Bugun ishlatilgan: {usage['count']}/{FREE_DAILY_REQUESTS} so'rov\n"
        f"⏱ Audio: {used_minutes}/{total_minutes} daqiqa\n"
        f"👥 Referallar: {referral_count} ta (+{bonus} daqiqa bonus)\n"
        f"🔗 Referal kodingiz: `{user['referral_code']}`"
    )
