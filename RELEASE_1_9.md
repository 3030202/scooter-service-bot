# Scooter Service Bot — Release 1.9 Release Notes

Release 1.9 introduces **Custom OpenAI-Compatible AI Provider Registration & Dynamic Remote Model Auto-Discovery**.

---

## 🌟 What's New in Release 1.9

### 1. 🤖 Custom OpenAI-Compatible Provider Management
- Register any custom OpenAI-compatible API provider (e.g. DeepSeek, Groq, OpenRouter, Local Ollama, vLLM, LocalAI, Qwen).
- Fully supports custom `base_url` and `api_key`.

### 2. ⚡ Automatic Model Discovery (`/v1/models`)
- Upon provider registration or manually via 1-click refresh, the bot automatically queries the provider's `{base_url}/models` endpoint using standard `client.models.list()`.
- Discovered models are stored in the database (`ai_models` table) and dynamically selected for text/vision diagnosis.

### 3. 🌐 REST API & Telegram Admin Dashboard
- **REST API Endpoints**:
  - `GET /api/ai/providers` — List registered AI providers, default active status, and discovered models.
  - `POST /api/ai/providers` — Register new provider and trigger model auto-fetch.
  - `POST /api/ai/providers/{id}/sync` — Re-sync available models list from provider.
- **Telegram Admin UI**:
  - Callback `admin:ai_providers` displays provider statuses.
  - Callback `admin:ai_sync:<provider_id>` triggers 1-click model refresh directly in chat.

---

## 📊 Database & Migration

- Added Alembic migration [0007_v19_ai_providers.py](file:///home/mx/scooter-service-bot/alembic/versions/0007_v19_ai_providers.py).
- Created tables `ai_providers` and `ai_models`.

---

## 🧪 Testing

- 37 unit and integration tests passing (`uv run pytest`):
  - `tests/test_ai_providers_integration.py`
  - `tests/test_ai_diagnostics_integration.py`
  - `tests/test_workload_calendar_integration.py`
