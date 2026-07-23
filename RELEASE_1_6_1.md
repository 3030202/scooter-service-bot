# Scooter Service Bot — Release 1.6.1 Release Notes

Release 1.6.1 introduces **Variant 6: Live Status Tracking & Master Repair Photo-Journal**.

---

## 🌟 What's New in Release 1.6.1

### 1. 📍 Live Status Tracking Progress Bar
- Clients can track repair progress in real time directly from Telegram chat:
  `[🟩 Приемка ➔ 🟩 Диагностика ➔ 🟨 Сборка ➔ ⬜ Тесты ➔ ⬜ Выдача]`
- Supported repair stages (`RepairStage`):
  1. `received` — 📥 Принят в сервис
  2. `diagnostics` — 🔍 Диагностика
  3. `parts_ordering` — 📦 Заказ запчастей
  4. `assembly` — 🔧 Сборка / Пайка
  5. `testing` — ⚡ Тестирование
  6. `ready` — 🏁 Готов к выдаче

### 2. 📸 Master Photo-Journal
- Masters can attach photo updates with custom captions for any active ticket.
- Photos are stored in the database (`RepairJournalEntry`) and automatically pushed to the client with live status updates.

### 3. 🚚 Preferred Pickup Method Selection
- Clients can toggle between `🚶 Самовывоз из сервиса` and `🚚 Доставка курьером`.

---

## 📊 Database & Migration

- Added Alembic migration [0004_v16_live_tracking.py](file:///home/mx/scooter-service-bot/alembic/versions/0004_v16_live_tracking.py).
- New Enum `RepairStage`.
- New table `repair_journal_entries`.
- Added `repair_stage` and `pickup_method` columns to `tickets`.

---

## 🧪 Testing

- 29 unit and integration tests passing (`uv run pytest`):
  - `tests/test_live_tracking_integration.py`
  - `tests/test_ticket_lifecycle_integration.py`
  - `tests/test_master_admin_flow_integration.py`
