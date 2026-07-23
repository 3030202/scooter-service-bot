import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

from aiogram.types import Message


class MediaGroupCollector:
    def __init__(self, wait_seconds: float) -> None:
        self.wait_seconds = wait_seconds
        self._messages: dict[str, list[Message]] = defaultdict(list)
        self._tasks: dict[str, asyncio.Task] = {}

    async def add(self, message: Message, callback: Callable[[list[Message]], Awaitable[None]]) -> None:
        if not message.media_group_id:
            await callback([message])
            return

        key = message.media_group_id
        self._messages[key].append(message)

        if key in self._tasks:
            self._tasks[key].cancel()

        self._tasks[key] = asyncio.create_task(self._flush_later(key, callback))

    async def _flush_later(self, key: str, callback: Callable[[list[Message]], Awaitable[None]]) -> None:
        try:
            await asyncio.sleep(self.wait_seconds)
            messages = self._messages.pop(key, [])
            self._tasks.pop(key, None)
            if messages:
                await callback(messages)
        except asyncio.CancelledError:
            return
