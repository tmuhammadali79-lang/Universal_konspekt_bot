import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Bot ──────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Admin ────────────────────────────────────────────
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# ── Database ─────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/bot.db")

# ── Free-tier limits ─────────────────────────────────
FREE_DAILY_REQUESTS = int(os.getenv("FREE_DAILY_REQUESTS", "3"))
FREE_DAILY_MINUTES = int(os.getenv("FREE_DAILY_MINUTES", "10"))
REFERRAL_BONUS_MINUTES = int(os.getenv("REFERRAL_BONUS_MINUTES", "5"))

# ── Premium ──────────────────────────────────────────
PREMIUM_STARS_PRICE = int(os.getenv("PREMIUM_STARS_PRICE", "100"))

# ── Paths ────────────────────────────────────────────
TEMP_DIR = BASE_DIR / "tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Whisper constraints ──────────────────────────────
MAX_FILE_SIZE_MB = 25  # Whisper limit
CHUNK_DURATION_SEC = 600  # 10 min chunks for large files

# ── GPT Model ────────────────────────────────────────
GPT_MODEL = "gpt-4o-mini"
WHISPER_MODEL = "whisper-1"

# ── Group settings ───────────────────────────────────
GROUP_VOICE_MIN_DURATION = int(os.getenv("GROUP_VOICE_MIN_DURATION", "30"))  # seconds
