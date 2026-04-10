"""SQLite database models and async helpers."""

import aiosqlite
from config import DB_PATH


async def init_db() -> None:
    """Create all tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                full_name     TEXT,
                language      TEXT    DEFAULT 'lat',
                ai_mode       TEXT    DEFAULT 'standard',
                is_premium    INTEGER DEFAULT 0,
                premium_until TEXT,
                is_blocked    INTEGER DEFAULT 0,
                referral_code TEXT    UNIQUE,
                referred_by   INTEGER,
                created_at    TEXT    DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                media_type      TEXT    NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                created_at      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                topic       TEXT,
                summary_text TEXT   NOT NULL,
                full_text   TEXT,
                media_type  TEXT,
                duration    INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()

        # ── Migration: add columns if missing ─────────
        try:
            await db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # column already exists


# ── User helpers ─────────────────────────────────────

async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(
    user_id: int,
    username: str | None,
    full_name: str,
    referral_code: str,
    referred_by: int | None = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO users
               (user_id, username, full_name, referral_code, referred_by)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, full_name, referral_code, referred_by),
        )
        await db.commit()


async def update_user_language(user_id: int, language: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language = ? WHERE user_id = ?",
            (language, user_id),
        )
        await db.commit()


async def update_user_mode(user_id: int, mode: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ai_mode = ? WHERE user_id = ?",
            (mode, user_id),
        )
        await db.commit()


async def set_premium(user_id: int, until: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?",
            (until, user_id),
        )
        await db.commit()


async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_total_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def block_user(user_id: int) -> None:
    """Block a user from using the bot."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blocked = 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def unblock_user(user_id: int) -> None:
    """Unblock a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_blocked = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def set_unlimited_premium(user_id: int) -> None:
    """Grant unlimited premium (no expiry)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_premium = 1, premium_until = 'unlimited' WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def remove_premium(user_id: int) -> None:
    """Remove premium from a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


# ── Usage log helpers ────────────────────────────────

async def log_usage(user_id: int, media_type: str, duration_seconds: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO usage_logs (user_id, media_type, duration_seconds)
               VALUES (?, ?, ?)""",
            (user_id, media_type, duration_seconds),
        )
        await db.commit()


async def get_today_usage(user_id: int) -> dict:
    """Return today's request count and total seconds used."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT COUNT(*), COALESCE(SUM(duration_seconds), 0)
               FROM usage_logs
               WHERE user_id = ? AND date(created_at) = date('now')""",
            (user_id,),
        )
        row = await cursor.fetchone()
        return {"count": row[0], "seconds": row[1]}


# ── Summary helpers ──────────────────────────────────

async def save_summary(
    user_id: int,
    topic: str,
    summary_text: str,
    full_text: str,
    media_type: str,
    duration: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO summaries
               (user_id, topic, summary_text, full_text, media_type, duration)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, topic, summary_text, full_text, media_type, duration),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_user_summaries(user_id: int, limit: int = 10, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM summaries
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_summary_by_id(summary_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_total_summaries() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM summaries")
        row = await cursor.fetchone()
        return row[0] if row else 0
