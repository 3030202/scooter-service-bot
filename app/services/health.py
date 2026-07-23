from __future__ import annotations

import asyncio

from aiohttp import web
from sqlalchemy import text

from app.config import settings
from app.db.session import engine
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


async def start_health_server() -> web.AppRunner | None:
    if not settings.observability_enabled:
        return None
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", metrics_view)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.health_host, settings.health_port)
    await site.start()
    return runner


async def stop_health_server(runner: web.AppRunner | None) -> None:
    if runner:
        await runner.cleanup()
        await asyncio.sleep(0)
