"""Auto-register middleware — ensures every user exists in DB."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from database.models import get_user, create_user
from utils.helpers import generate_referral_code


class UserMiddleware(BaseMiddleware):
    """Outer middleware: auto-registers users and injects user record."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Extract user from the event
        user_tg = None
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                user_tg = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                user_tg = event.callback_query.from_user

        if user_tg and not user_tg.is_bot:
            user = await get_user(user_tg.id)
            if not user:
                await create_user(
                    user_id=user_tg.id,
                    username=user_tg.username,
                    full_name=user_tg.full_name,
                    referral_code=generate_referral_code(),
                )
                user = await get_user(user_tg.id)
            data["db_user"] = user

        return await handler(event, data)
