# Scooter Service Bot — Release 1.8 Release Notes

Release 1.8 introduces **Variant 8: Interactive Master Workload & Schedule Calendar Manager**.

---

## 🌟 What's New in Release 1.8

### 1. 📅 Master Workload Visualization
- Interactive schedule dashboard for admins and masters displaying total allocated hours and percentage load:
  `[👤 Пётр: 🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜ 50% (4.5 ч / 3 слота)]`
- Calculates capacity based on configurable working hours (`WORKDAY_START_HOUR` and `WORKDAY_END_HOUR`).

### 2. 🤖 Smart Master Assignment & Load Balancing
- Intelligent slot reservation algorithm (`recommend_smart_slot`) balancing incoming repair requests to masters with lowest current workload.

### 3. 🚫 Administrative Slot Blocking
- Support for non-ticket administrative time blocks (`note` field in `calendar_slots`).
- Allows admins/masters to block slots for lunch breaks, maintenance, or emergency leave.

---

## 📊 Database & Migration

- Added Alembic migration [0006_v18_workload_calendar.py](file:///home/mx/scooter-service-bot/alembic/versions/0006_v18_workload_calendar.py).
- Made `calendar_slots.ticket_id` nullable.
- Added `note` column to `calendar_slots`.

---

## 🧪 Testing

- 34 unit and integration tests passing (`uv run pytest`):
  - `tests/test_workload_calendar_integration.py`
  - `tests/test_payments_integration.py`
  - `tests/test_live_tracking_integration.py`
