"""Smart Summary AI Bot — main entry point."""

import asyncio
import logging
import sys
import shutil

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database.models import init_db
from middlewares.user_middleware import UserMiddleware
from middlewares.throttle_middleware import ThrottleMiddleware
from handlers import start, voice, links, history, premium, admin, group

# ── Logging ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def check_dependencies() -> None:
    """Verify required system dependencies."""
    if not shutil.which("ffmpeg"):
        logger.warning(
            "⚠️  FFmpeg not found! Audio processing will not work. "
            "Install from https://ffmpeg.org/download.html"
        )
    if not shutil.which("yt-dlp"):
        logger.warning(
            "⚠️  yt-dlp not found! YouTube/Instagram downloads will not work. "
            "Install with: pip install yt-dlp"
        )


async def main() -> None:
    """Initialize and start the bot."""
    # ── Checks ───────────────────────────────────────
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please configure .env file.")
        sys.exit(1)

    check_dependencies()

    # ── Database ─────────────────────────────────────
    logger.info("Initializing database...")
    await init_db()

    # ── Bot & Dispatcher ─────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # ── Middlewares ───────────────────────────────────
    dp.update.outer_middleware(UserMiddleware())
    dp.message.middleware(ThrottleMiddleware(cooldown=3.0))

    # ── Routers (order matters! links router last since it catches all text) ──
    dp.include_router(start.router)
    dp.include_router(voice.router)
    dp.include_router(history.router)
    dp.include_router(premium.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)   # group voice auto-summary
    dp.include_router(links.router)   # must be last — catches all text messages

    # ── Start ────────────────────────────────────────
    logger.info("Smart Summary AI Bot is starting...")
    bot_info = await bot.get_me()
    logger.info("Bot: @%s (id: %d)", bot_info.username, bot_info.id)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
