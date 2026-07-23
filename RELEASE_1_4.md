# Release 1.4 — Automated Retention Scheduler & Push Dispatcher

Release 1.4 introduces automated background processing and proactive Telegram push notifications for retention reminders (`retention_reminders`).

---

## 🚀 Key Features Added

1. **Background Retention Worker (`app/services/retention.py`)**
   - Automatically polls for due unsent retention reminders (`due_at <= now()`).
   - Dispatches interactive Telegram notifications directly to clients.
   - Attaches inline quick-action buttons (`🛴 Создать заявку`, `📋 Мои заявки`).
   - Automatically marks processed reminders as `is_sent = True`.

2. **Configurable Environment Settings (`app/config.py`)**
   - `RETENTION_AUTO_SEND_ENABLED`: Master toggle for automated retention dispatches (default: `True`).
   - `RETENTION_CHECK_INTERVAL_SECONDS`: Loop sleep interval in seconds (default: `60`).
   - `RETENTION_BATCH_SIZE`: Maximum reminders processed per batch (default: `20`).

3. **Resilience & Observability**
   - Handles `TelegramForbiddenError` / `TelegramBadRequest` (e.g. if client blocked the bot or chat not found) without interrupting the loop or crashing the service.
   - Extends Prometheus metrics (`/metrics`) with:
     - `scooter_bot_retention_auto_sent_total`
     - `scooter_bot_retention_failed_total`

4. **Lifecycle Integration (`app/main.py`)**
   - Background worker starts automatically when the bot initializes and shuts down cleanly on SIGTERM/SIGINT.

---

## 🧪 Validation

```bash
uv run pytest
```
