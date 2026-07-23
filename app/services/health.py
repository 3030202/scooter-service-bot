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


async def start_health_server() -> web.AppRunner | None:
    if not settings.observability_enabled:
        return None
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics_view)
    app.router.add_get("/webapp/client", webapp_client_view)
    app.router.add_get("/webapp/master", webapp_master_view)
    app.router.add_get("/api/catalog", api_catalog_view)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.health_host, settings.health_port)
    await site.start()
    return runner


async def stop_health_server(runner: web.AppRunner | None) -> None:
    if runner:
        await runner.cleanup()
        await asyncio.sleep(0)
