"""Reply keyboards for main menu."""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main persistent menu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📜 Tarix"),
                KeyboardButton(text="📊 Statistika"),
            ],
            [
                KeyboardButton(text="🤖 AI Rejim"),
                KeyboardButton(text="⭐ Premium"),
            ],
            [
                KeyboardButton(text="⚙️ Sozlamalar"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Ovozli xabar yuboring yoki link tashlang...",
    )
