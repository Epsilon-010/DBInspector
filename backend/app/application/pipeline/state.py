from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from app.domain.conversation import ConversationTurn
from app.domain.models import (
    AnalysisResult,
    GuardrailVerdict,
    QueryResult,
    Question,
    SchemaSnapshot,
    SQLQuery,
)


@dataclass(slots=True)
class PipelineState:
    question: Question
    history: tuple[ConversationTurn, ...] = ()
    verdict: GuardrailVerdict | None = None
    schema: SchemaSnapshot | None = None
    sql: SQLQuery | None = None
    last_sql_error: str | None = None
    sql_attempt: int = 0
    result: QueryResult | None = None
    processed_rows: list[dict[str, Any]] = field(default_factory=list)
    analysis: AnalysisResult | None = None

    def with_(self, **changes: Any) -> PipelineState:
        return replace(self, **changes)
