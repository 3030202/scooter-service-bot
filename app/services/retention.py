from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from app.config import settings
from app.db.models import RetentionReminder, User
from app.db.session import AsyncSessionLocal
from app.services.crm import due_retention_items
from app.services.metrics import metrics

if TYPE_CHECKING:
    from aiogram import Bot


def retention_client_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛴 Создать заявку", callback_data="client:new_ticket"),
                InlineKeyboardButton(text="📋 Мои заявки", callback_data="client:my_tickets"),
            ]
        ]
    )


async def process_due_retention_reminders(bot: Bot) -> int:
    """Fetches unsent due retention reminders and dispatches them to clients via Telegram."""
    processed_count = 0
    async with AsyncSessionLocal() as session:
        due_items = await due_retention_items(session, limit=settings.retention_batch_size)
        if not due_items:
            return 0

        logger.info(f"Processing {len(due_items)} due retention reminders")
        for reminder in due_items:
            client = await session.get(User, reminder.client_id)
            if not client or not client.telegram_id:
                logger.warning(f"Client missing or has no telegram_id for retention reminder #{reminder.id}")
                reminder.is_sent = True
                await session.commit()
                metrics.inc("retention_failed_total")
                continue

            text = (
                f"🔧 Напоминание от сервиса:\n\n"
                f"{reminder.message}\n\n"
                f"Хотите записаться на проверку или сезонное ТО?"
            )

            try:
                await bot.send_message(
                    chat_id=client.telegram_id,
                    text=text,
                    reply_markup=retention_client_keyboard(),
                )
                reminder.is_sent = True
                await session.commit()
                processed_count += 1
                metrics.inc("retention_sent_total")
                metrics.inc("retention_auto_sent_total")
                logger.info(f"Retention reminder #{reminder.id} sent to client {client.telegram_id}")
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                logger.warning(f"Failed to send retention #{reminder.id} to user {client.telegram_id} (bot blocked/invalid): {e}")
                reminder.is_sent = True
                await session.commit()
                metrics.inc("retention_failed_total")
            except Exception as e:
                logger.error(f"Unexpected error sending retention reminder #{reminder.id}: {e}")
                metrics.inc("retention_failed_total")

    return processed_count


async def _retention_worker_loop(bot: Bot) -> None:
    logger.info("Retention scheduler worker started")
    while True:
        try:
            if settings.retention_auto_send_enabled:
                await process_due_retention_reminders(bot)
            await asyncio.sleep(settings.retention_check_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Retention scheduler worker cancelled")
            break
        except Exception as e:
            logger.error(f"Error in retention scheduler loop: {e}")
            await asyncio.sleep(settings.retention_check_interval_seconds)


def start_retention_scheduler(bot: Bot) -> asyncio.Task:
    """Launches the retention scheduler loop as a background asyncio task."""
    return asyncio.create_task(_retention_worker_loop(bot))
