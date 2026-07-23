from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger

from app.services.metrics import metrics


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            metrics.inc("errors_total")
            logger.exception("Unhandled update error: {}", exc)

            target = None
            if isinstance(event, Message):
                target = event
            elif isinstance(event, CallbackQuery):
                await event.answer("Ошибка обработки. Попробуйте позже.", show_alert=True)
                target = event.message

            if target:
                await target.answer("⚠️ Сервис временно не смог обработать действие. Попробуйте еще раз или нажмите /start.")
            return None
