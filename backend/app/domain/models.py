from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Question(FrozenBase):
    text: str = Field(..., min_length=1, max_length=2000)


class GuardrailVerdict(FrozenBase):
    is_safe: bool
    reason: str


class ColumnInfo(FrozenBase):
    name: str
    data_type: str
    nullable: bool


class TableInfo(FrozenBase):
    name: str
    schema_name: str
    columns: tuple[ColumnInfo, ...]


class SchemaSnapshot(FrozenBase):
    tables: tuple[TableInfo, ...]

    def to_prompt_string(self) -> str:
        lines: list[str] = []
        for table in self.tables:
            qualified = f"{table.schema_name}.{table.name}"
            cols = ", ".join(
                f"{c.name} {c.data_type}{'' if c.nullable else ' NOT NULL'}"
                for c in table.columns
            )
            lines.append(f"{qualified}({cols})")
        return "\n".join(lines)


class SQLQuery(FrozenBase):
    sql: str = Field(..., min_length=1)


class QueryResult(FrozenBase):
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    row_count: int
    truncated: bool = False

    def to_dict_rows(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row, strict=True)) for row in self.rows]


ChartType = Literal["bar", "line", "pie", "scatter", "table"]


class ChartSpec(FrozenBase):
    type: ChartType
    x: str | None
    y: str | None
    series: str | None = None
    title: str


class AnalysisResult(FrozenBase):
    summary: str
    chart: ChartSpec


class FinalReport(FrozenBase):
    question: Question
    sql: SQLQuery
    result: QueryResult
    analysis: AnalysisResult
