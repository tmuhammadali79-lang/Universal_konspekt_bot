"""Inline keyboards for the bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def summary_keyboard(summary_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown after a summary is generated."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📄 To'liq matnni ko'rish",
                callback_data=f"full_text:{summary_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Mening statistikam",
                callback_data="my_stats",
            ),
            InlineKeyboardButton(
                text="⭐ Premium",
                callback_data="premium_info",
            ),
        ],
    ])


def history_keyboard(summaries: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    """Paginated summary history."""
    buttons: list[list[InlineKeyboardButton]] = []

    for s in summaries:
        topic = s.get("topic", "Nomsiz")[:40]
        buttons.append([
            InlineKeyboardButton(
                text=f"📝 {topic}",
                callback_data=f"view_summary:{s['id']}",
            )
        ])

    # Navigation
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"history_page:{page - 1}"))
    if len(summaries) == 10:  # might have more
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"history_page:{page + 1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def premium_keyboard(bot_username: str, referral_code: str) -> InlineKeyboardMarkup:
    """Premium info and referral sharing."""
    referral_link = f"https://t.me/{bot_username}?start=ref_{referral_code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⭐ Premium sotib olish",
                callback_data="buy_premium",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📎 Referal linkni ulashish",
                switch_inline_query=f"Smart Summary AI botidan foydalaning! {referral_link}",
            ),
        ],
    ])


def language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 Lotin", callback_data="set_lang:lat"),
            InlineKeyboardButton(text="🇺🇿 Кирилл", callback_data="set_lang:kir"),
        ],
    ])


def mode_keyboard(current_mode: str = "standard") -> InlineKeyboardMarkup:
    """AI mode selection keyboard."""
    modes = [
        ("standard", "📝 Standart"),
        ("talaba", "🎓 Talaba"),
        ("biznes", "💼 Biznes"),
        ("bloger", "🎬 Bloger"),
    ]

    buttons: list[list[InlineKeyboardButton]] = []
    for mode_id, label in modes:
        mark = " ✅" if mode_id == current_mode else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{label}{mark}",
                callback_data=f"set_mode:{mode_id}",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def limit_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown when user hits daily limit."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⭐ Premium sotib olish",
                callback_data="buy_premium",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Statistikam",
                callback_data="my_stats",
            ),
            InlineKeyboardButton(
                text="⭐ Premium haqida",
                callback_data="premium_info",
            ),
        ],
    ])
