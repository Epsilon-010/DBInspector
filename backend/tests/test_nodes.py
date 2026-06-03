from __future__ import annotations

import pytest

from app.application.pipeline.nodes.analyzer import AnalyzerNode
from app.application.pipeline.nodes.data_processor import DataProcessorNode
from app.application.pipeline.nodes.guardrail import GuardrailNode
from app.application.pipeline.nodes.sql_executor import SQLExecutorNode
from app.application.pipeline.nodes.sql_generator import (
    SQLGeneratorNode,
    _strip_fences,
)
from app.application.pipeline.state import PipelineState
from app.domain.errors import QueryExecutionError, UnsafeQueryError
from app.domain.models import (
    GuardrailVerdict,
    QueryResult,
    SQLQuery,
)

from tests.conftest import FakeDatabase, FakeIntrospector, FakeLLM, FakeValidator


# ---------- GuardrailNode ---------- #


class TestGuardrailNode:
    async def test_accepts_safe_question(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(guardrail_safe=True, guardrail_reason="all good")
        node = GuardrailNode(llm)
        new_state = await node.run(sample_state)
        assert new_state.verdict == GuardrailVerdict(is_safe=True, reason="all good")

    async def test_marks_unsafe_question(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(guardrail_safe=False, guardrail_reason="injection")
        new_state = await GuardrailNode(llm).run(sample_state)
        assert new_state.verdict is not None
        assert new_state.verdict.is_safe is False
        assert new_state.verdict.reason == "injection"


# ---------- SQLGeneratorNode + _strip_fences ---------- #


class TestStripFences:
    def test_no_fences_passthrough(self) -> None:
        assert _strip_fences("SELECT 1") == "SELECT 1"

    def test_strips_sql_fence(self) -> None:
        assert _strip_fences("```sql\nSELECT 1\n```") == "SELECT 1"

    def test_strips_bare_fence(self) -> None:
        assert _strip_fences("```\nSELECT 1\n```") == "SELECT 1"

    def test_strips_trailing_semicolon(self) -> None:
        assert _strip_fences("SELECT 1;") == "SELECT 1"


class TestSQLGeneratorNode:
    async def test_first_call_uses_initial_prompt(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(sql_outputs=["SELECT 1"])
        introspector = FakeIntrospector()
        node = SQLGeneratorNode(llm, introspector)
        new_state = await node.run(sample_state)

        assert new_state.sql == SQLQuery(sql="SELECT 1")
        assert new_state.sql_attempt == 1
        assert new_state.schema is not None
        assert introspector.calls == 1
        # No retry prompt on first call
        sent = llm.complete_calls[0]["user"]
        assert "previous SQL attempt failed" not in sent
        assert "Database schema:" in sent

    async def test_retry_call_includes_previous_error_and_sql(
        self, sample_state: PipelineState
    ) -> None:
        llm = FakeLLM(sql_outputs=["SELECT 2"])
        introspector = FakeIntrospector()
        state = sample_state.with_(
            sql=SQLQuery(sql="SELECT broken"),
            last_sql_error="syntax error at 'broken'",
        )
        node = SQLGeneratorNode(llm, introspector)
        new_state = await node.run(state)

        assert new_state.sql_attempt == 1  # increments from 0; orchestrator owns the counter mainly
        sent = llm.complete_calls[0]["user"]
        assert "previous SQL attempt failed" in sent
        assert "SELECT broken" in sent
        assert "syntax error at 'broken'" in sent

    async def test_reuses_cached_schema_if_present(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(sql_outputs=["SELECT 1"])
        introspector = FakeIntrospector()
        first = await SQLGeneratorNode(llm, introspector).run(sample_state)
        assert introspector.calls == 1

        # Second call with state.schema already set: introspector NOT called again
        await SQLGeneratorNode(llm, introspector).run(first)
        assert introspector.calls == 1


# ---------- SQLExecutorNode ---------- #


class TestSQLExecutorNode:
    async def test_runs_validator_then_database(self, sample_state: PipelineState) -> None:
        db = FakeDatabase()
        validator = FakeValidator()
        state = sample_state.with_(sql=SQLQuery(sql="SELECT id FROM t"))
        node = SQLExecutorNode(db, validator, timeout_seconds=5, max_rows=100)

        new_state = await node.run(state)

        assert validator.received[0].sql == "SELECT id FROM t"
        assert db.received[0].sql == "SELECT id FROM t"
        assert new_state.result is not None
        assert new_state.last_sql_error is None

    async def test_validator_failure_propagates(self, sample_state: PipelineState) -> None:
        db = FakeDatabase()
        validator = FakeValidator(raise_on={"DROP TABLE t"})
        state = sample_state.with_(sql=SQLQuery(sql="DROP TABLE t"))
        node = SQLExecutorNode(db, validator, timeout_seconds=5, max_rows=100)

        with pytest.raises(UnsafeQueryError):
            await node.run(state)
        assert db.calls == 0  # never reached the database

    async def test_database_failure_propagates(self, sample_state: PipelineState) -> None:
        db = FakeDatabase(fail_count=1)
        state = sample_state.with_(sql=SQLQuery(sql="SELECT 1"))
        node = SQLExecutorNode(db, FakeValidator(), timeout_seconds=5, max_rows=100)

        with pytest.raises(QueryExecutionError):
            await node.run(state)

    async def test_raises_when_no_sql_in_state(self, sample_state: PipelineState) -> None:
        node = SQLExecutorNode(FakeDatabase(), FakeValidator(), timeout_seconds=5, max_rows=100)
        with pytest.raises(RuntimeError, match="without a generated SQL"):
            await node.run(sample_state)


# ---------- DataProcessorNode ---------- #


class TestDataProcessorNode:
    async def test_converts_result_to_dict_rows(self, sample_state: PipelineState) -> None:
        result = QueryResult(
            columns=("id", "name"), rows=((1, "a"), (2, "b")), row_count=2
        )
        state = sample_state.with_(result=result)
        new_state = await DataProcessorNode().run(state)
        assert new_state.processed_rows == [
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
        ]

    async def test_handles_empty_result(self, sample_state: PipelineState) -> None:
        result = QueryResult(columns=("id",), rows=(), row_count=0)
        state = sample_state.with_(result=result)
        new_state = await DataProcessorNode().run(state)
        assert new_state.processed_rows == []

    async def test_raises_when_no_result_in_state(self, sample_state: PipelineState) -> None:
        with pytest.raises(RuntimeError, match="without a query result"):
            await DataProcessorNode().run(sample_state)


# ---------- AnalyzerNode ---------- #


class TestAnalyzerNode:
    async def _state_with_result(self, sample_state: PipelineState) -> PipelineState:
        return sample_state.with_(
            sql=SQLQuery(sql="SELECT id FROM t"),
            result=QueryResult(columns=("id",), rows=((1,),), row_count=1),
            processed_rows=[{"id": 1}],
        )

    async def test_happy_payload(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(
            analyzer_payload={
                "summary": "Hay 1 fila.",
                "chart": {"type": "bar", "x": "id", "y": "id", "series": None, "title": "T"},
            }
        )
        state = await self._state_with_result(sample_state)
        new_state = await AnalyzerNode(llm).run(state)
        assert new_state.analysis is not None
        assert new_state.analysis.summary == "Hay 1 fila."
        assert new_state.analysis.chart.type == "bar"
        assert new_state.analysis.chart.title == "T"

    async def test_invalid_chart_type_falls_back_to_table(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(
            analyzer_payload={
                "summary": "x",
                "chart": {"type": "histogram", "x": None, "y": None, "title": ""},
            }
        )
        state = await self._state_with_result(sample_state)
        new_state = await AnalyzerNode(llm).run(state)
        assert new_state.analysis is not None
        assert new_state.analysis.chart.type == "table"
        assert new_state.analysis.chart.title == "Resultados"  # default when empty

    async def test_missing_chart_payload_uses_table(self, sample_state: PipelineState) -> None:
        llm = FakeLLM(analyzer_payload={"summary": "ok"})
        state = await self._state_with_result(sample_state)
        new_state = await AnalyzerNode(llm).run(state)
        assert new_state.analysis is not None
        assert new_state.analysis.chart.type == "table"

    async def test_raises_when_no_result_or_sql(self, sample_state: PipelineState) -> None:
        with pytest.raises(RuntimeError, match="without a result/SQL"):
            await AnalyzerNode(FakeLLM()).run(sample_state)
