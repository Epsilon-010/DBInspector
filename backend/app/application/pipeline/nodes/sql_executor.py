from __future__ import annotations

from app.application.pipeline.state import PipelineState
from app.application.ports.database import Database
from app.application.ports.sql_validator import SQLValidator


class SQLExecutorNode:
    name = "sql_executor"

    def __init__(
        self,
        database: Database,
        validator: SQLValidator,
        *,
        timeout_seconds: int,
        max_rows: int,
    ) -> None:
        self._database = database
        self._validator = validator
        self._timeout_seconds = timeout_seconds
        self._max_rows = max_rows

    async def run(self, state: PipelineState) -> PipelineState:
        if state.sql is None:
            raise RuntimeError("SQLExecutorNode invoked without a generated SQL query")

        self._validator.validate(state.sql)
        result = await self._database.execute(
            state.sql,
            timeout_seconds=self._timeout_seconds,
            max_rows=self._max_rows,
        )
        return state.with_(result=result, last_sql_error=None)
