import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.metrics import metrics


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = max(1, limit_per_minute)
        self.window_seconds = 60
        self.events: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        bucket = self.events[user.id]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.limit:
            metrics.inc("rate_limited_total")
            if isinstance(event, Message):
                await event.answer("Слишком много сообщений. Подождите минуту и повторите.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Слишком много действий. Подождите минуту.", show_alert=True)
            return None

        bucket.append(now)
        return await handler(event, data)
