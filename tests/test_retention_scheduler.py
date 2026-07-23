from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.db.models import RetentionReminder, User
from app.services.retention import process_due_retention_reminders, retention_client_keyboard


def test_retention_client_keyboard():
    kb = retention_client_keyboard()
    buttons = [b.text for row in kb.inline_keyboard for b in row]
    assert "🛴 Создать заявку" in buttons
    assert "📋 Мои заявки" in buttons


@pytest.mark.asyncio
async def test_process_due_retention_reminders_no_items():
    mock_bot = AsyncMock()
    with patch("app.services.retention.due_retention_items", new_callable=AsyncMock) as mock_due:
        mock_due.return_value = []
        processed = await process_due_retention_reminders(mock_bot)
        assert processed == 0
        mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_due_retention_reminders_success():
    mock_bot = AsyncMock()
    mock_user = User(id=1, telegram_id=999888777, full_name="Test User")
    mock_reminder = RetentionReminder(
        id=10,
        client_id=1,
        ticket_id=5,
        kind="post_repair_checkup",
        due_at=datetime.now(timezone.utc) - timedelta(days=1),
        message="Тестовое ТО",
        is_sent=False,
    )

    mock_session = AsyncMock()

    async def mock_get(model, item_id):
        if model == User and item_id == 1:
            return mock_user
        return None

    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.commit = AsyncMock()

    with patch("app.services.retention.due_retention_items", new_callable=AsyncMock) as mock_due, \
         patch("app.services.retention.AsyncSessionLocal") as mock_session_local:
        
        mock_due.return_value = [mock_reminder]
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        mock_session_local.return_value = mock_session_ctx

        processed = await process_due_retention_reminders(mock_bot)

        assert processed == 1
        assert mock_reminder.is_sent is True
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 999888777
        assert "Тестовое ТО" in call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_process_due_retention_reminders_blocked_user():
    mock_bot = AsyncMock()
    mock_bot.send_message.side_effect = TelegramForbiddenError(
        method=MagicMock(), message="Forbidden: bot was blocked by the user"
    )
    mock_user = User(id=2, telegram_id=111222333, full_name="Blocked User")
    mock_reminder = RetentionReminder(
        id=11,
        client_id=2,
        ticket_id=6,
        kind="post_repair_checkup",
        due_at=datetime.now(timezone.utc) - timedelta(days=1),
        message="Проверка аккумулятора",
        is_sent=False,
    )

    mock_session = AsyncMock()

    async def mock_get(model, item_id):
        if model == User and item_id == 2:
            return mock_user
        return None

    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.commit = AsyncMock()

    with patch("app.services.retention.due_retention_items", new_callable=AsyncMock) as mock_due, \
         patch("app.services.retention.AsyncSessionLocal") as mock_session_local:
        
        mock_due.return_value = [mock_reminder]
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        mock_session_local.return_value = mock_session_ctx

        processed = await process_due_retention_reminders(mock_bot)

        assert processed == 0
        assert mock_reminder.is_sent is True
        mock_bot.send_message.assert_called_once()
