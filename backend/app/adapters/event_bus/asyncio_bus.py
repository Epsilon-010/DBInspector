from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.application.ports.event_bus import EventBus, EventBusFactory
from app.domain.events import PipelineEvent

_SENTINEL: object = object()


class AsyncioEventBus(EventBus):
    def __init__(self, maxsize: int = 64) -> None:
        self._queue: asyncio.Queue[PipelineEvent | object] = asyncio.Queue(maxsize=maxsize)
        self._closed = False

    async def publish(self, event: PipelineEvent) -> None:
        if self._closed:
            return
        await self._queue.put(event)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._queue.put(_SENTINEL)

    async def stream(self) -> AsyncIterator[PipelineEvent]:
        while True:
            item = await self._queue.get()
            if item is _SENTINEL:
                return
            yield item  # type: ignore[misc]


class AsyncioEventBusFactory(EventBusFactory):
    def create(self, request_id: str) -> EventBus:
        del request_id
        return AsyncioEventBus()
