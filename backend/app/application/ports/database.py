from __future__ import annotations

from typing import Protocol

from app.domain.models import QueryResult, SchemaSnapshot, SQLQuery


class SchemaIntrospector(Protocol):
    async def snapshot(self) -> SchemaSnapshot: ...


class Database(Protocol):
    async def execute(
        self,
        query: SQLQuery,
        *,
        timeout_seconds: int,
        max_rows: int,
    ) -> QueryResult: ...
