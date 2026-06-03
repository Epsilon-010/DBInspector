from __future__ import annotations

import asyncio

from app.adapters.event_bus.asyncio_bus import AsyncioEventBus
from app.api.session_manager import SessionManager
from app.domain.models import (
    AnalysisResult,
    ChartSpec,
    FinalReport,
    QueryResult,
    Question,
    SQLQuery,
)


def _make_report() -> FinalReport:
    return FinalReport(
        question=Question(text="q"),
        sql=SQLQuery(sql="SELECT 1"),
        result=QueryResult(columns=("x",), rows=((1,),), row_count=1),
        analysis=AnalysisResult(
            summary="s",
            chart=ChartSpec(type="table", x=None, y=None, title="t"),
        ),
    )


async def _completed_task(value: FinalReport | None) -> FinalReport | None:
    return value


async def _failing_task() -> FinalReport | None:
    raise RuntimeError("boom")


async def test_register_returns_unique_ids() -> None:
    sm = SessionManager()
    bus1, bus2 = AsyncioEventBus(), AsyncioEventBus()
    t1 = asyncio.create_task(_completed_task(_make_report()))
    t2 = asyncio.create_task(_completed_task(_make_report()))
    rid1 = await sm.register(bus1, t1)
    rid2 = await sm.register(bus2, t2)
    await asyncio.gather(t1, t2)
    assert rid1 != rid2


async def test_get_bus_returns_registered_bus() -> None:
    sm = SessionManager()
    bus = AsyncioEventBus()
    task = asyncio.create_task(_completed_task(_make_report()))
    rid = await sm.register(bus, task)
    await task
    assert (await sm.get_bus(rid)) is bus


async def test_get_bus_unknown_id_returns_none() -> None:
    sm = SessionManager()
    assert (await sm.get_bus("doesnotexist")) is None


async def test_get_report_waits_for_completion() -> None:
    sm = SessionManager()
    bus = AsyncioEventBus()
    report = _make_report()

    async def slow_task() -> FinalReport | None:
        await asyncio.sleep(0.05)
        return report

    task = asyncio.create_task(slow_task())
    rid = await sm.register(bus, task)
    got = await sm.get_report(rid)
    assert got is report


async def test_get_report_returns_none_on_task_exception() -> None:
    sm = SessionManager()
    bus = AsyncioEventBus()
    task = asyncio.create_task(_failing_task())
    rid = await sm.register(bus, task)
    got = await sm.get_report(rid)
    assert got is None


async def test_discard_removes_session() -> None:
    sm = SessionManager()
    bus = AsyncioEventBus()
    task = asyncio.create_task(_completed_task(_make_report()))
    rid = await sm.register(bus, task)
    await task
    await sm.discard(rid)
    assert (await sm.get_bus(rid)) is None


async def test_lru_eviction_drops_oldest_when_over_cap() -> None:
    sm = SessionManager(max_sessions=2)
    tasks = []
    ids: list[str] = []
    for _ in range(3):
        bus = AsyncioEventBus()
        t = asyncio.create_task(_completed_task(_make_report()))
        tasks.append(t)
        ids.append(await sm.register(bus, t))
    await asyncio.gather(*tasks)

    assert (await sm.get_bus(ids[0])) is None  # evicted
    assert (await sm.get_bus(ids[1])) is not None
    assert (await sm.get_bus(ids[2])) is not None


async def test_get_outcome_unknown_id_returns_none() -> None:
    sm = SessionManager()
    assert (await sm.get_outcome("nope")) is None


async def test_get_outcome_returns_report_on_success() -> None:
    sm = SessionManager()
    report = _make_report()
    task = asyncio.create_task(_completed_task(report))
    rid = await sm.register(AsyncioEventBus(), task)
    outcome = await sm.get_outcome(rid)
    assert outcome is not None
    assert outcome.report is report
    assert outcome.error is None


async def test_get_outcome_captures_error_when_task_crashes() -> None:
    sm = SessionManager()
    task = asyncio.create_task(_failing_task())
    rid = await sm.register(AsyncioEventBus(), task)
    outcome = await sm.get_outcome(rid)
    assert outcome is not None
    assert outcome.report is None
    assert outcome.error is not None
    assert "RuntimeError" in outcome.error
    assert "boom" in outcome.error


async def test_lru_keeps_recently_accessed() -> None:
    sm = SessionManager(max_sessions=2)
    tasks = []
    ids: list[str] = []
    for _ in range(2):
        bus = AsyncioEventBus()
        t = asyncio.create_task(_completed_task(_make_report()))
        tasks.append(t)
        ids.append(await sm.register(bus, t))

    # Touch ids[0] so it becomes most-recent
    await sm.get_bus(ids[0])

    # Insert a third → ids[1] (LRU) should be evicted, not ids[0]
    bus3 = AsyncioEventBus()
    t3 = asyncio.create_task(_completed_task(_make_report()))
    tasks.append(t3)
    id3 = await sm.register(bus3, t3)
    await asyncio.gather(*tasks)

    assert (await sm.get_bus(ids[1])) is None
    assert (await sm.get_bus(ids[0])) is not None
    assert (await sm.get_bus(id3)) is not None
