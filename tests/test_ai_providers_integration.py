from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db.models import AIModel, AIProvider
from app.services.ai_provider_service import get_active_ai_service_client, register_provider, set_default_provider, sync_provider_models


@pytest.mark.asyncio
async def test_register_provider_and_auto_fetch_models(db_session):
    mock_models = ["deepseek-chat", "deepseek-reasoner"]

    with patch("app.services.ai_provider_service.fetch_models_from_endpoint", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_models

        provider, models = await register_provider(
            db_session,
            name="DeepSeek Test",
            base_url="https://api.deepseek.com/v1",
            api_key="sk-deepseek-123",
            set_as_default=True,
            fetch_models=True,
        )
        await db_session.commit()

        assert provider.id is not None
        assert provider.name == "DeepSeek Test"
        assert provider.is_default is True
        assert len(models) == 2
        assert models[0].model_name == "deepseek-chat"


@pytest.mark.asyncio
async def test_get_active_ai_service_client(db_session):
    provider = AIProvider(
        name="Groq Test",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk-123",
        is_active=True,
        is_default=True,
    )
    db_session.add(provider)
    await db_session.commit()

    model = AIModel(provider_id=provider.id, model_name="llama-3.3-70b-versatile", is_active=True)
    db_session.add(model)
    await db_session.commit()

    client, model_name = await get_active_ai_service_client(db_session)
    assert model_name == "llama-3.3-70b-versatile"
    assert str(client.base_url) == "https://api.groq.com/openai/v1/"


@pytest.mark.asyncio
async def test_sync_provider_models(db_session):
    provider = AIProvider(
        name="Local vLLM",
        base_url="http://localhost:8000/v1",
        api_key="none",
        is_active=True,
    )
    db_session.add(provider)
    await db_session.commit()

    old_model = AIModel(provider_id=provider.id, model_name="old-model-7b", is_active=True)
    db_session.add(old_model)
    await db_session.commit()

    with patch("app.services.ai_provider_service.fetch_models_from_endpoint", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = ["qwen-2.5-72b-instruct", "mistral-large"]

        new_models = await sync_provider_models(db_session, provider.id)
        await db_session.commit()

        assert len(new_models) == 2
        model_names = [m.model_name for m in new_models]
        assert "qwen-2.5-72b-instruct" in model_names
        assert "mistral-large" in model_names
