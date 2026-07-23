import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from loguru import logger

from app.config import settings
from app.handlers import client, master
from app.logging import setup_logging
from app.middlewares import ErrorMiddleware, RateLimitMiddleware
from app.services.health import start_health_server, stop_health_server
from app.services.metrics import metrics
from app.services.retention import start_retention_scheduler


async def run_migrations() -> None:
    if not settings.run_migrations_on_startup:
        return

    logger.info("Applying Alembic migrations")
    process = await asyncio.create_subprocess_exec(
        "alembic",
        "upgrade",
        "head",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if stdout:
        logger.info(stdout.decode().strip())
    if stderr:
        logger.warning(stderr.decode().strip())
    if process.returncode != 0:
        raise RuntimeError(f"Alembic failed with exit code {process.returncode}")


async def main() -> None:
    setup_logging()
    logger.info("Starting scooter service bot")

    await run_migrations()

    health_runner = await start_health_server()
    bot = Bot(token=settings.bot_token)
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    errors = ErrorMiddleware()
    rate_limit = RateLimitMiddleware(settings.rate_limit_per_minute)
    dp.update.outer_middleware(errors)
    dp.message.outer_middleware(rate_limit)
    dp.callback_query.outer_middleware(rate_limit)

    dp.include_router(master.router)
    dp.include_router(client.router)

    retention_task = start_retention_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    metrics.inc("starts_total")
    try:
        await dp.start_polling(bot)
    finally:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        await storage.close()
        await stop_health_server(health_runner)


if __name__ == "__main__":
    asyncio.run(main())
