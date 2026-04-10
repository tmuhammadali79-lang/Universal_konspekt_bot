"""Utility functions: URL detection, formatting, referral codes."""

import re
import uuid


# ── URL patterns ─────────────────────────────────────
YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"[\w\-]+"
)

INSTAGRAM_RE = re.compile(
    r"(https?://)?(www\.)?"
    r"instagram\.com/(reel|reels|p)/[\w\-]+"
)


def extract_youtube_url(text: str) -> str | None:
    m = YOUTUBE_RE.search(text)
    return m.group(0) if m else None


def extract_instagram_url(text: str) -> str | None:
    m = INSTAGRAM_RE.search(text)
    return m.group(0) if m else None


def detect_url_type(text: str) -> tuple[str, str] | None:
    """Return (type, url) or None."""
    yt = extract_youtube_url(text)
    if yt:
        return ("youtube", yt)
    ig = extract_instagram_url(text)
    if ig:
        return ("instagram", ig)
    return None


# ── Formatting helpers ───────────────────────────────

def format_duration(seconds: int) -> str:
    """Convert seconds → mm:ss or hh:mm:ss."""
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def truncate(text: str, max_len: int = 4000) -> str:
    """Truncate text to fit Telegram message limit."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def generate_referral_code() -> str:
    """Short unique referral code."""
    return uuid.uuid4().hex[:8]
