from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.domain.events import PipelineEvent


class EventBus(Protocol):
    async def publish(self, event: PipelineEvent) -> None: ...

    async def close(self) -> None: ...

    def stream(self) -> AsyncIterator[PipelineEvent]: ...


class EventBusFactory(Protocol):
    def create(self, request_id: str) -> EventBus: ...
