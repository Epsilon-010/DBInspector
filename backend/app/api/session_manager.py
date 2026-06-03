from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from app.application.ports.event_bus import EventBus
from app.domain.models import FinalReport


@dataclass(frozen=True, slots=True)
class SessionOutcome:
    report: FinalReport | None
    error: str | None


@dataclass(slots=True)
class _Session:
    bus: EventBus
    task: asyncio.Task[FinalReport | None]
    report: FinalReport | None = None
    error: str | None = None
    finished: asyncio.Event = field(default_factory=asyncio.Event)


class SessionManager:
    def __init__(self, max_sessions: int = 100) -> None:
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_sessions = max_sessions

    @staticmethod
    def next_request_id() -> str:
        return uuid.uuid4().hex

    async def register(
        self,
        bus: EventBus,
        task: asyncio.Task[FinalReport | None],
        *,
        request_id: str | None = None,
    ) -> str:
        rid = request_id or self.next_request_id()
        session = _Session(bus=bus, task=task)

        async with self._lock:
            self._sessions[rid] = session
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)

        def _on_done(t: asyncio.Task[FinalReport | None]) -> None:
            try:
                session.report = t.result()
            except Exception as exc:  # noqa: BLE001 - surface failures, do not swallow control-flow
                session.error = f"{type(exc).__name__}: {exc}"
            finally:
                session.finished.set()

        task.add_done_callback(_on_done)
        return rid

    async def get_bus(self, request_id: str) -> EventBus | None:
        async with self._lock:
            session = self._sessions.get(request_id)
            if session is not None:
                self._sessions.move_to_end(request_id)
        return session.bus if session else None

    async def get_outcome(self, request_id: str) -> SessionOutcome | None:
        async with self._lock:
            session = self._sessions.get(request_id)
            if session is not None:
                self._sessions.move_to_end(request_id)
        if session is None:
            return None
        await session.finished.wait()
        return SessionOutcome(report=session.report, error=session.error)

    async def get_report(self, request_id: str) -> FinalReport | None:
        outcome = await self.get_outcome(request_id)
        return outcome.report if outcome else None

    async def discard(self, request_id: str) -> None:
        async with self._lock:
            self._sessions.pop(request_id, None)
