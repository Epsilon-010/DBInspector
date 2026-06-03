from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.application.pipeline.state import PipelineState
from app.domain.events import PipelineEventType, ProgressEvent, RejectedEvent
from app.domain.models import (
    ChartSpec,
    ColumnInfo,
    QueryResult,
    Question,
    SchemaSnapshot,
    SQLQuery,
    TableInfo,
)


class TestQuestion:
    def test_accepts_normal_text(self) -> None:
        q = Question(text="¿Top 5 productos?")
        assert q.text == "¿Top 5 productos?"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            Question(text="")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Question(text="x" * 2001)

    def test_is_frozen(self) -> None:
        q = Question(text="hi")
        with pytest.raises(ValidationError):
            q.text = "bye"  # type: ignore[misc]


class TestSchemaSnapshot:
    def test_to_prompt_string_qualifies_and_marks_not_null(self) -> None:
        snap = SchemaSnapshot(
            tables=(
                TableInfo(
                    name="orders",
                    schema_name="public",
                    columns=(
                        ColumnInfo(name="id", data_type="integer", nullable=False),
                        ColumnInfo(name="note", data_type="text", nullable=True),
                    ),
                ),
            )
        )
        out = snap.to_prompt_string()
        assert "public.orders(" in out
        assert "id integer NOT NULL" in out
        assert "note text" in out
        assert "note text NOT NULL" not in out

    def test_to_prompt_string_lists_multiple_tables_on_separate_lines(self) -> None:
        snap = SchemaSnapshot(
            tables=(
                TableInfo(
                    name="a", schema_name="s",
                    columns=(ColumnInfo(name="x", data_type="int", nullable=False),),
                ),
                TableInfo(
                    name="b", schema_name="s",
                    columns=(ColumnInfo(name="y", data_type="int", nullable=True),),
                ),
            )
        )
        assert snap.to_prompt_string().splitlines() == ["s.a(x int NOT NULL)", "s.b(y int)"]


class TestQueryResult:
    def test_to_dict_rows_pairs_columns(self) -> None:
        result = QueryResult(
            columns=("id", "name"),
            rows=((1, "alpha"), (2, "beta")),
            row_count=2,
        )
        assert result.to_dict_rows() == [
            {"id": 1, "name": "alpha"},
            {"id": 2, "name": "beta"},
        ]

    def test_to_dict_rows_empty(self) -> None:
        result = QueryResult(columns=("id",), rows=(), row_count=0)
        assert result.to_dict_rows() == []


class TestChartSpec:
    def test_rejects_unknown_type(self) -> None:
        with pytest.raises(ValidationError):
            ChartSpec(type="histogram", x="a", y="b", title="t")  # type: ignore[arg-type]

    def test_accepts_known_types(self) -> None:
        for t in ("bar", "line", "pie", "scatter", "table"):
            ChartSpec(type=t, x=None, y=None, title="t")  # type: ignore[arg-type]


class TestPipelineState:
    def test_with_returns_new_instance(self, sample_question: Question) -> None:
        a = PipelineState(question=sample_question)
        b = a.with_(sql=SQLQuery(sql="SELECT 1"))
        assert a is not b
        assert a.sql is None
        assert b.sql is not None
        assert b.sql.sql == "SELECT 1"

    def test_with_preserves_unchanged_fields(self, sample_question: Question) -> None:
        a = PipelineState(question=sample_question, sql_attempt=3)
        b = a.with_(last_sql_error="boom")
        assert b.sql_attempt == 3
        assert b.question is sample_question


class TestEvents:
    def test_progress_event_defaults(self) -> None:
        evt = ProgressEvent(stage="x", message="hi")
        assert evt.type == PipelineEventType.PROGRESS
        assert evt.attempt == 1
        assert evt.payload == {}

    def test_rejected_event_has_fixed_type(self) -> None:
        evt = RejectedEvent(reason="no")
        assert evt.type == PipelineEventType.REJECTED
