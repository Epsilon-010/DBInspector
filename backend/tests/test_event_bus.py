from __future__ import annotations

import asyncio

from app.adapters.event_bus.asyncio_bus import AsyncioEventBus
from app.domain.events import ProgressEvent, ResultEvent


async def _drain(bus: AsyncioEventBus) -> list:
    return [evt async for evt in bus.stream()]


async def test_stream_yields_published_events_then_stops_on_close() -> None:
    bus = AsyncioEventBus()
    await bus.publish(ProgressEvent(stage="a", message="hi"))
    await bus.publish(ProgressEvent(stage="b", message="hi"))
    await bus.close()

    events = await _drain(bus)
    assert [e.stage for e in events] == ["a", "b"]


async def test_close_is_idempotent() -> None:
    bus = AsyncioEventBus()
    await bus.publish(ProgressEvent(stage="a", message="hi"))
    await bus.close()
    await bus.close()  # second close must not hang nor raise

    events = await _drain(bus)
    assert len(events) == 1


async def test_publish_after_close_is_dropped_silently() -> None:
    bus = AsyncioEventBus()
    await bus.close()
    await bus.publish(ProgressEvent(stage="late", message="x"))

    events = await _drain(bus)
    assert events == []


async def test_stream_consumer_can_run_concurrently_with_producer() -> None:
    bus = AsyncioEventBus()

    async def produce() -> None:
        for i in range(3):
            await bus.publish(ProgressEvent(stage=f"s{i}", message="m"))
            await asyncio.sleep(0)
        await bus.publish(ResultEvent(report={"ok": True}))
        await bus.close()

    consumer = asyncio.create_task(_drain(bus))
    await produce()
    events = await consumer
    assert [type(e).__name__ for e in events] == [
        "ProgressEvent",
        "ProgressEvent",
        "ProgressEvent",
        "ResultEvent",
    ]
