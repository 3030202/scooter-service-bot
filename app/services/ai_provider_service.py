from loguru import logger
from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AIModel, AIProvider


async def fetch_models_from_endpoint(base_url: str, api_key: str) -> list[str]:
    try:
        client = AsyncOpenAI(api_key=api_key or "no-key", base_url=base_url)
        response = await client.models.list()
        model_names = [model.id for model in response.data]
        logger.info(f"Auto-discovered {len(model_names)} models from {base_url}")
        return model_names
    except Exception as exc:
        logger.warning(f"Failed to auto-discover models from {base_url}: {exc}")
        return []


async def register_provider(
    session: AsyncSession,
    name: str,
    base_url: str,
    api_key: str,
    set_as_default: bool = False,
    fetch_models: bool = True,
) -> tuple[AIProvider, list[AIModel]]:
    if set_as_default:
        await session.execute(update(AIProvider).values(is_default=False))

    provider = AIProvider(
        name=name,
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        is_active=True,
        is_default=set_as_default,
    )
    session.add(provider)
    await session.flush()

    models_created: list[AIModel] = []
    if fetch_models:
        model_names = await fetch_models_from_endpoint(base_url, api_key)
        for m_name in model_names:
            ai_model = AIModel(provider_id=provider.id, model_name=m_name, is_active=True)
            session.add(ai_model)
            models_created.append(ai_model)

    await session.flush()
    return provider, models_created


async def sync_provider_models(session: AsyncSession, provider_id: int) -> list[AIModel]:
    provider = await session.get(AIProvider, provider_id)
    if not provider:
        raise ValueError(f"Provider #{provider_id} not found")

    model_names = await fetch_models_from_endpoint(provider.base_url, provider.api_key)

    # Delete existing models for this provider
    existing = (await session.scalars(select(AIModel).where(AIModel.provider_id == provider.id))).all()
    for item in existing:
        await session.delete(item)

    created: list[AIModel] = []
    for m_name in model_names:
        ai_model = AIModel(provider_id=provider.id, model_name=m_name, is_active=True)
        session.add(ai_model)
        created.append(ai_model)

    await session.flush()
    return created


async def set_default_provider(session: AsyncSession, provider_id: int) -> AIProvider:
    provider = await session.get(AIProvider, provider_id)
    if not provider:
        raise ValueError(f"Provider #{provider_id} not found")

    await session.execute(update(AIProvider).values(is_default=False))
    provider.is_default = True
    provider.is_active = True
    await session.flush()
    return provider


async def get_active_ai_service_client(session: AsyncSession | None = None) -> tuple[AsyncOpenAI, str]:
    if session is not None:
        try:
            # Query default active provider
            provider = await session.scalar(
                select(AIProvider).where(AIProvider.is_active == True, AIProvider.is_default == True)
            )
            if not provider:
                # Query any active provider
                provider = await session.scalar(select(AIProvider).where(AIProvider.is_active == True))

            if provider:
                # Find first active model
                model = await session.scalar(
                    select(AIModel).where(AIModel.provider_id == provider.id, AIModel.is_active == True)
                )
                model_name = model.model_name if model else settings.ai_text_model
                client = AsyncOpenAI(api_key=provider.api_key, base_url=provider.base_url)
                return client, model_name
        except Exception as exc:
            logger.warning(f"Error fetching AI provider from DB: {exc}")

    # Default fallback to settings
    client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url)
    return client, settings.ai_text_model
