"""Anti-flood throttle middleware."""

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message


class ThrottleMiddleware(BaseMiddleware):
    """Simple per-user cooldown to prevent spam."""

    def __init__(self, cooldown: float = 3.0) -> None:
        self.cooldown = cooldown
        self._last: Dict[int, float] = {}
        self._cleanup_counter = 0

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.monotonic()
        last = self._last.get(user_id, 0)

        if now - last < self.cooldown:
            # Silently ignore — too fast
            return None

        self._last[user_id] = now

        # Periodic cleanup: every 100 messages, remove stale entries
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup_counter = 0
            cutoff = now - self.cooldown * 2
            self._last = {uid: ts for uid, ts in self._last.items() if ts > cutoff}

        return await handler(event, data)
