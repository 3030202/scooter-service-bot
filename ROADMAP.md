# Scooter Service Bot — Product & Technical Roadmap

This roadmap documents the strategic improvement vectors identified during architectural and business analysis.

---

## 🗺️ Improvement Vectors

### 1. 🔔 Variant 1: Automated Retention Scheduler & Push Dispatcher
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
- **Status**: Implemented with 26 passing E2E integration test cases.

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
- **Status**: Implemented in Release 1.6.

---

### 5. 💳 Variant 5: Telegram Payments & Prepayment Integration
- **Goal**: Enable direct digital payment and deposits inside Telegram chat upon quote approval.
- **Key Features**:
  - Integration with Telegram Payments API (Yookassa / Telegram Stars / Tinkoff Pay).
  - Invoice generation upon client approval of ticket final price.
  - Automatic status transition to `in_progress` upon verified payment webhook.
- **Status**: Implemented in Release 1.7.

---

### 6. 📸 Variant 6: Live Status Tracking & Master Repair Photo-Journal
- **Goal**: Provide real-time repair stage tracking and photo updates for clients.
- **Key Features**:
  - Live progress bar: `Принято` ➔ `Диагностика` ➔ `Заказ запчастей` ➔ `Сборка` ➔ `Готов к выдаче`.
  - Master photo journal: 1-click attachment of repair progress photos (before vs after).
  - Choice of pickup method: Self-pickup vs Courier delivery.
- **Status**: Implemented in Release 1.6.1.

---

### 7. 📦 Variant 7: Warehouse Inventory Management & Low-Stock Alerts
- **Goal**: Track spare part stock levels and calculate repair profit margins.
- **Key Features**:
  - Inventory table (`inventory_items`) tracking stock counts, reorder thresholds, and wholesale costs.
  - Automatic deduction of stock when master adds items to ticket estimate.
  - Automated low-stock alert notifications to admins when items drop below threshold.
  - Auto-calculation of repair margin (Total Price - Spare Part Cost).

---

### 8. 📅 Variant 8: Interactive Master Workload & Schedule Calendar Manager
- **Goal**: Visualize master availability and optimize slot scheduling without double-booking.
- **Key Features**:
  - Interactive WebApp calendar grid showing hourly/daily load per master.
  - Smart master assignment based on current workload and catalog item duration (`default_eta`).
  - Emergency slot blocking (e.g. master sick leave or holiday).
- **Status**: Implemented in Release 1.8.

---

### 9. 📊 Variant 9: Business Analytics, Financial Reports & CRM Integration
- **Goal**: Export financial and operational metrics for business owners.
- **Key Features**:
  - `/export_stats` command generating Excel/PDF summary reports.
  - Revenue by category, top frequent faults, customer LTV, and master performance.
  - Webhook integration with external CRM/ERP platforms (Moysklad / 1C / Bitrix24).

---

### 10. 🔒 Variant 10: Multi-Branch & Franchise Support
- **Goal**: Support multiple service center locations and franchise branches within a single bot instance.
- **Key Features**:
  - Branch selection for clients based on geolocation or city district.
  - Branch-isolated ticket queues, master whitelists, and catalog pricing tiers.
  - Multi-tenant admin dashboard.

---

### 11. 🤖 Variant 11: Custom OpenAI-Compatible Providers & Dynamic Auto-Discovery
- **Goal**: Register custom LLM endpoints (DeepSeek, Groq, OpenRouter, Local Ollama/vLLM) and auto-discover models from `/v1/models`.
- **Key Features**:
  - Auto-discovery of remote models list via OpenAI SDK `client.models.list()`.
  - Database persistence (`ai_providers` & `ai_models`).
  - REST API (`GET/POST /api/ai/providers`) & Telegram Admin Dashboard (`admin:ai_providers`).
- **Status**: Implemented in Release 1.9.
