from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.errors import QueryExecutionError
from app.domain.models import QueryResult, SQLQuery


class PostgresDatabase:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def execute(
        self,
        query: SQLQuery,
        *,
        timeout_seconds: int,
        max_rows: int,
    ) -> QueryResult:
        timeout_ms = timeout_seconds * 1000
        try:
            async with self._engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                    await conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
                    result = await asyncio.wait_for(
                        conn.exec_driver_sql(query.sql),
                        timeout=timeout_seconds + 1,
                    )
                    columns = tuple(result.keys())
                    fetched = result.fetchmany(max_rows + 1)
                    truncated = len(fetched) > max_rows
                    rows = tuple(tuple(row) for row in fetched[:max_rows])
                    return QueryResult(
                        columns=columns,
                        rows=rows,
                        row_count=len(rows),
                        truncated=truncated,
                    )
                finally:
                    await trans.rollback()
        except TimeoutError as exc:
            raise QueryExecutionError(
                f"Query excedió el timeout de {timeout_seconds}s"
            ) from exc
        except SQLAlchemyError as exc:
            raise QueryExecutionError(_short_db_error(exc)) from exc


def _short_db_error(exc: SQLAlchemyError) -> str:
    msg = str(getattr(exc, "orig", exc))
    return msg.splitlines()[0][:500]
