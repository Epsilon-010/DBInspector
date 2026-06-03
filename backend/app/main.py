from __future__ import annotations

import asyncio
import json
import sys

from app.adapters.event_bus.asyncio_bus import AsyncioEventBus
from app.composition import Container
from app.config import load_settings
from app.domain.events import PipelineEventType
from app.domain.models import Question


async def _run(question_text: str) -> int:
    settings = load_settings()
    container = Container.build(settings)
    bus = AsyncioEventBus()
    orchestrator = container.make_orchestrator(bus)

    consumer_task = asyncio.create_task(_print_events(bus))
    try:
        report = await orchestrator.run(Question(text=question_text))
    finally:
        await consumer_task
        await container.shutdown()

    if report is None:
        return 1

    print("\n=== FINAL REPORT ===")
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2, default=str))
    return 0


async def _print_events(bus: AsyncioEventBus) -> None:
    async for event in bus.stream():
        if event.type == PipelineEventType.PROGRESS:
            print(f"[{event.stage}] (try {event.attempt}) {event.message}")
        elif event.type == PipelineEventType.REJECTED:
            print(f"[REJECTED] {event.reason}")
        elif event.type == PipelineEventType.FAILED:
            print(f"[FAILED:{event.stage}] {event.error}")
        elif event.type == PipelineEventType.RESULT:
            print("[RESULT] received")


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m app.main "<your question>"', file=sys.stderr)
        raise SystemExit(2)
    question_text = " ".join(sys.argv[1:])
    raise SystemExit(asyncio.run(_run(question_text)))


if __name__ == "__main__":
    main()
