import os
from aiohttp import web
from sqlalchemy import text

from app.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.services.catalog import list_catalog, seed_catalog
from app.services.metrics import metrics


async def healthz(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def readyz(_: web.Request) -> web.Response:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return web.json_response({"status": "ready"})
    except Exception as exc:
        return web.json_response({"status": "not_ready", "error": str(exc)}, status=503)


async def metrics_view(_: web.Request) -> web.Response:
    return web.Response(text=metrics.render_prometheus(), content_type="text/plain")


async def webapp_client_view(_: web.Request) -> web.Response:
    path = os.path.join(os.path.dirname(__file__), "..", "webapp", "client.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")
    return web.Response(text="Client WebApp not found", status=404)


async def webapp_master_view(_: web.Request) -> web.Response:
    path = os.path.join(os.path.dirname(__file__), "..", "webapp", "master.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")
    return web.Response(text="Master WebApp not found", status=404)


async def api_catalog_view(_: web.Request) -> web.Response:
    async with AsyncSessionLocal() as session:
        await seed_catalog(session)
        items = await list_catalog(session, limit=50)
        data = [
            {
                "id": item.id,
                "code": item.code,
                "title": item.title,
                "category": item.category,
                "base_price": float(item.base_price),
                "default_eta": item.default_eta or "1 день",
            }
            for item in items
        ]
        return web.json_response(data)


async def api_ai_providers_list_view(_: web.Request) -> web.Response:
    from sqlalchemy import select
    from app.db.models import AIModel, AIProvider

    async with AsyncSessionLocal() as session:
        providers = (await session.scalars(select(AIProvider))).all()
        result = []
        for prov in providers:
            models = (await session.scalars(select(AIModel).where(AIModel.provider_id == prov.id))).all()
            result.append({
                "id": prov.id,
                "name": prov.name,
                "base_url": prov.base_url,
                "is_active": prov.is_active,
                "is_default": prov.is_default,
                "models_count": len(models),
                "models": [m.model_name for m in models],
            })
        return web.json_response(result)


async def api_ai_provider_register_view(request: web.Request) -> web.Response:
    from app.services.ai_provider_service import register_provider

    try:
        data = await request.json()
        name = data.get("name", "Custom AI Provider")
        base_url = data.get("base_url", "").strip()
        api_key = data.get("api_key", "").strip()
        set_as_default = bool(data.get("set_as_default", False))

        if not base_url:
            return web.json_response({"error": "base_url is required"}, status=400)

        async with AsyncSessionLocal() as session:
            provider, models = await register_provider(
                session, name, base_url, api_key, set_as_default=set_as_default, fetch_models=True
            )
            await session.commit()

            return web.json_response({
                "status": "created",
                "provider_id": provider.id,
                "name": provider.name,
                "base_url": provider.base_url,
                "is_default": provider.is_default,
                "models_discovered_count": len(models),
                "models": [m.model_name for m in models],
            }, status=201)

    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=500)


from typing import TYPE_CHECKING
from loguru import logger
from sqlalchemy import select
from app.db.models import Ticket, TicketStatus, User, UserRole
from app.keyboards.inline import contact_keyboard

if TYPE_CHECKING:
    from aiogram import Bot


async def api_webapp_client_select_view(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        telegram_id = data.get("telegram_id")
        init_data_unsafe = data.get("initDataUnsafe")
        if not telegram_id and isinstance(init_data_unsafe, dict):
            telegram_id = init_data_unsafe.get("user", {}).get("id")

        node = data.get("node", "Узел поломки")
        details = data.get("details", "")
        description = f"Выбор поломки WebApp: {node}. {details}".strip()

        if not telegram_id:
            return web.json_response({"error": "telegram_id missing"}, status=400)

        bot = request.app.get("bot")
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.telegram_id == int(telegram_id)))
            if not user:
                user = User(telegram_id=int(telegram_id), role=UserRole.CLIENT)
                session.add(user)
                await session.flush()

            ticket = Ticket(
                client_id=user.id,
                status=TicketStatus.WAITING_PHOTOS,
                description=description,
            )
            session.add(ticket)
            await session.commit()

            if bot:
                try:
                    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                    reply_kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="✨ Получить расчёт AI", callback_data=f"client:run_ai:{ticket.id}")],
                            [InlineKeyboardButton(text="📱 Отправить контакт", callback_data=f"client:add_phone:{ticket.id}")],
                        ]
                    )
                    await bot.send_message(
                        chat_id=int(telegram_id),
                        text=(
                            f"✅ **Данные из WebApp получены!**\n\n"
                            f"🛠 **Узел неисправности**: {node}\n"
                            f"📝 **Детали**: {details or 'Не указано'}\n\n"
                            "Вы можете отправить фото поломки в чат или сразу получить предварительный расчёт AI:"
                        ),
                        reply_markup=reply_kb,
                    )
                except Exception as b_err:
                    logger.warning("Could not send Telegram confirmation for WebApp: {}", b_err)

            return web.json_response({"status": "ok", "ticket_id": ticket.id})
    except Exception as exc:
        logger.exception("Error handling WebApp client selection: {}", exc)
        return web.json_response({"error": str(exc)}, status=500)


async def start_health_server(bot: "Bot | None" = None) -> web.AppRunner | None:
    if not settings.observability_enabled:
        return None
    app = web.Application()
    if bot:
        app["bot"] = bot
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics_view)
    app.router.add_get("/webapp/client", webapp_client_view)
    app.router.add_get("/webapp/master", webapp_master_view)
    app.router.add_post("/api/webapp/client_select", api_webapp_client_select_view)
    app.router.add_get("/api/catalog", api_catalog_view)
    app.router.add_get("/api/ai/providers", api_ai_providers_list_view)
    app.router.add_post("/api/ai/providers", api_ai_provider_register_view)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.health_host, settings.health_port)
    await site.start()
    return runner


async def stop_health_server(runner: web.AppRunner | None) -> None:
    if runner:
        await runner.cleanup()
        await asyncio.sleep(0)
