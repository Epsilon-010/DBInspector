from __future__ import annotations

import asyncio
import time

from app.application.ports.database import SchemaIntrospector
from app.domain.models import SchemaSnapshot


class CachingSchemaIntrospector:
    def __init__(self, inner: SchemaIntrospector, ttl_seconds: float = 300.0) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._cached: SchemaSnapshot | None = None
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    async def snapshot(self) -> SchemaSnapshot:
        if self._is_fresh():
            return self._cached  # type: ignore[return-value]
        async with self._lock:
            if self._is_fresh():
                return self._cached  # type: ignore[return-value]
            self._cached = await self._inner.snapshot()
            self._cached_at = time.monotonic()
            return self._cached

    async def invalidate(self) -> None:
        async with self._lock:
            self._cached = None
            self._cached_at = 0.0

    def _is_fresh(self) -> bool:
        if self._cached is None:
            return False
        return (time.monotonic() - self._cached_at) < self._ttl
