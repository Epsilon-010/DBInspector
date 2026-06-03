"""Shared fakes: implement the application/ports/* protocols without touching infra."""
from __future__ import annotations

import pytest

from app.application.pipeline.state import PipelineState
from app.domain.errors import QueryExecutionError
from app.domain.models import (
    ColumnInfo,
    QueryResult,
    Question,
    SchemaSnapshot,
    SQLQuery,
    TableInfo,
)


class FakeLLM:
    """LLMClient that returns scripted responses."""

    def __init__(
        self,
        *,
        guardrail_safe: bool = True,
        guardrail_reason: str = "ok",
        sql_outputs: list[str] | None = None,
        analyzer_payload: dict | None = None,
    ) -> None:
        self._guardrail_safe = guardrail_safe
        self._guardrail_reason = guardrail_reason
        self._sql_outputs = sql_outputs or ["SELECT id FROM products LIMIT 5"]
        self._sql_idx = 0
        self._analyzer_payload = analyzer_payload or {
            "summary": "Resumen ejecutivo de prueba.",
            "chart": {"type": "bar", "x": "id", "y": "id", "series": None, "title": "Demo"},
        }
        self.complete_calls: list[dict] = []
        self.complete_json_calls: list[dict] = []

    async def complete(
        self, *, system: str, user: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        self.complete_calls.append({"system": system, "user": user})
        sql = self._sql_outputs[min(self._sql_idx, len(self._sql_outputs) - 1)]
        self._sql_idx += 1
        return sql

    async def complete_json(
        self, *, system: str, user: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> dict:
        self.complete_json_calls.append({"system": system, "user": user})
        if "guardrail" in system.lower():
            return {"is_safe": self._guardrail_safe, "reason": self._guardrail_reason}
        return self._analyzer_payload


class FakeIntrospector:
    def __init__(self, snapshot: SchemaSnapshot | None = None) -> None:
        self._snapshot = snapshot or SchemaSnapshot(
            tables=(
                TableInfo(
                    name="products",
                    schema_name="public",
                    columns=(
                        ColumnInfo(name="id", data_type="integer", nullable=False),
                        ColumnInfo(name="name", data_type="text", nullable=True),
                    ),
                ),
            )
        )
        self.calls = 0

    async def snapshot(self) -> SchemaSnapshot:
        self.calls += 1
        return self._snapshot


class FakeDatabase:
    """Fails the first `fail_count` calls with QueryExecutionError, then succeeds."""

    def __init__(self, fail_count: int = 0, result: QueryResult | None = None) -> None:
        self._fail_count = fail_count
        self._result = result or QueryResult(
            columns=("id", "name"),
            rows=((1, "alpha"), (2, "beta")),
            row_count=2,
            truncated=False,
        )
        self.calls = 0
        self.received: list[SQLQuery] = []

    async def execute(
        self, query: SQLQuery, *, timeout_seconds: int, max_rows: int
    ) -> QueryResult:
        self.calls += 1
        self.received.append(query)
        if self.calls <= self._fail_count:
            raise QueryExecutionError("simulated db error")
        return self._result


class FakeValidator:
    def __init__(self, *, raise_on: set[str] | None = None) -> None:
        self._raise_on = raise_on or set()
        self.received: list[SQLQuery] = []

    def validate(self, query: SQLQuery) -> None:
        self.received.append(query)
        if query.sql in self._raise_on:
            from app.domain.errors import UnsafeQueryError

            raise UnsafeQueryError(f"rejected: {query.sql}")


@pytest.fixture
def sample_question() -> Question:
    return Question(text="¿Cuáles son los 5 productos más vendidos este año?")


@pytest.fixture
def sample_state(sample_question: Question) -> PipelineState:
    return PipelineState(question=sample_question)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_introspector() -> FakeIntrospector:
    return FakeIntrospector()


@pytest.fixture
def fake_database() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def fake_validator() -> FakeValidator:
    return FakeValidator()
