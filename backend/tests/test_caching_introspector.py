from __future__ import annotations

import asyncio

from app.adapters.db.caching_introspector import CachingSchemaIntrospector
from app.domain.models import ColumnInfo, SchemaSnapshot, TableInfo


def _snapshot() -> SchemaSnapshot:
    return SchemaSnapshot(
        tables=(
            TableInfo(
                name="t",
                schema_name="public",
                columns=(ColumnInfo(name="id", data_type="int", nullable=False),),
            ),
        )
    )


class _SpyInspector:
    def __init__(self) -> None:
        self.calls = 0

    async def snapshot(self) -> SchemaSnapshot:
        self.calls += 1
        await asyncio.sleep(0)
        return _snapshot()


async def test_first_call_delegates_then_caches() -> None:
    inner = _SpyInspector()
    caching = CachingSchemaIntrospector(inner, ttl_seconds=60.0)

    a = await caching.snapshot()
    b = await caching.snapshot()
    c = await caching.snapshot()

    assert inner.calls == 1
    assert a is b is c


async def test_expired_cache_refetches() -> None:
    inner = _SpyInspector()
    caching = CachingSchemaIntrospector(inner, ttl_seconds=0.0)  # always expired

    await caching.snapshot()
    await caching.snapshot()
    assert inner.calls == 2


async def test_invalidate_forces_refetch() -> None:
    inner = _SpyInspector()
    caching = CachingSchemaIntrospector(inner, ttl_seconds=60.0)

    await caching.snapshot()
    await caching.invalidate()
    await caching.snapshot()
    assert inner.calls == 2


async def test_concurrent_first_calls_only_trigger_one_underlying_call() -> None:
    """The asyncio.Lock prevents a thundering herd on cold cache."""
    inner = _SpyInspector()
    caching = CachingSchemaIntrospector(inner, ttl_seconds=60.0)

    results = await asyncio.gather(*(caching.snapshot() for _ in range(20)))
    assert inner.calls == 1
    assert all(r is results[0] for r in results)
