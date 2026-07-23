# Scooter Service Bot — Product & Technical Roadmap

This roadmap documents the 5 strategic improvement vectors identified during architectural analysis.

---

## 🗺️ Improvement Vectors

### 1. 🔔 Variant 1: Automated Retention Scheduler & Push Dispatcher (In Progress)
- **Goal**: Automatically send due retention messages (`retention_reminders`) to clients without requiring manual admin triggers.
- **Key Features**:
  - Background `asyncio` task checking for due unsent reminders (`due_at <= now()`).
  - Configurable interval, batch size, and auto-send toggle in `.env`.
  - Interactive Telegram inline keyboard attached to push notifications (`🛴 Записаться на ТО`, `💬 Поддержка`).
  - Robust exception handling for blocked users (`TelegramForbiddenError`) and full Prometheus metrics.
- **Status**: Implemented in Release 1.4.

---

### 2. 🧪 Variant 2: Comprehensive Integration & E2E Test Suite
- **Goal**: Expand test coverage beyond unit tests to cover full handler flows, FSM state transitions, and database interactions.
- **Key Features**:
  - Async integration tests using `pytest-asyncio` and `aiosqlite`/in-memory database.
  - Handler lifecycle testing (`draft` ➔ `waiting_photos` ➔ `ai_analysis` ➔ `diagnosed` ➔ `assigned` ➔ `done`).
  - Mocked Telegram API interactions for `Client` and `Master` routers.

---

### 3. 📱 Variant 3: Telegram Mini App (WebApp) for Master Estimate Builder & Client Showcase
- **Goal**: Replace multi-step inline keyboard pagination with rich, interactive WebApp interfaces.
- **Key Features**:
  - **Master WebApp**: Interactive quote/estimate builder with catalog checkboxes, custom spare part inputs, dynamic total recalculation, and calendar date-picker.
  - **Client WebApp**: Visual scooter node picker (battery, controller, motor wheel, brakes) with photo drag-and-drop.
- **Status**: Implemented in Release 1.5.

---

### 4. 🤖 Variant 4: Catalog-Matched AI Diagnostics & Structured Output Parser
- **Goal**: Integrate OpenAI Structured Outputs (`pydantic` JSON schema enforcement) to match AI fault descriptions directly to catalog service items.
- **Key Features**:
  - AI analysis returns specific recommended `ServiceCatalogItem` codes.
  - Exponential backoff retry & graceful fallback when LLM API is unavailable.
  - Automatic pre-selection of catalog items during ticket creation.

---

### 5. 💳 Variant 5: Telegram Payments & Prepayment Integration
- **Goal**: Enable direct digital payment and deposits inside Telegram chat upon quote approval.
- **Key Features**:
  - Integration with Telegram Payments API (Yookassa / Telegram Stars / Tinkoff Pay).
  - Invoice generation upon client approval of ticket final price.
  - Automatic status transition to `in_progress` upon verified payment webhook.
