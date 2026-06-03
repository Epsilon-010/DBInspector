from __future__ import annotations

import json
from typing import Annotated

import strawberry

from app.domain.conversation import Conversation, ConversationTurn
from app.domain.events import (
    FailedEvent,
    PipelineEvent,
    PipelineEventType,
    ProgressEvent,
    RejectedEvent,
)
from app.domain.models import AnalysisResult, ChartSpec, FinalReport, QueryResult


@strawberry.type
class RunQueryHandle:
    request_id: strawberry.ID


@strawberry.type
class ChartSpecGQL:
    type: str
    x: str | None
    y: str | None
    series: str | None
    title: str

    @classmethod
    def from_domain(cls, spec: ChartSpec) -> ChartSpecGQL:
        return cls(type=spec.type, x=spec.x, y=spec.y, series=spec.series, title=spec.title)


@strawberry.type
class AnalysisGQL:
    summary: str
    chart: ChartSpecGQL

    @classmethod
    def from_domain(cls, analysis: AnalysisResult) -> AnalysisGQL:
        return cls(summary=analysis.summary, chart=ChartSpecGQL.from_domain(analysis.chart))


@strawberry.type
class QueryResultGQL:
    columns: list[str]
    row_count: int
    truncated: bool
    rows_json: str

    @classmethod
    def from_domain(cls, result: QueryResult) -> QueryResultGQL:
        return cls(
            columns=list(result.columns),
            row_count=result.row_count,
            truncated=result.truncated,
            rows_json=json.dumps(result.to_dict_rows(), ensure_ascii=False, default=str),
        )


@strawberry.type
class ConversationHandleGQL:
    id: strawberry.ID


@strawberry.type
class FinalReportGQL:
    question: str
    sql: str
    result: QueryResultGQL
    analysis: AnalysisGQL

    @classmethod
    def from_domain(cls, report: FinalReport) -> FinalReportGQL:
        return cls(
            question=report.question.text,
            sql=report.sql.sql,
            result=QueryResultGQL.from_domain(report.result),
            analysis=AnalysisGQL.from_domain(report.analysis),
        )


@strawberry.type
class ConversationTurnGQL:
    created_at: str
    report: FinalReportGQL

    @classmethod
    def from_domain(cls, turn: ConversationTurn) -> ConversationTurnGQL:
        return cls(
            created_at=turn.created_at.isoformat(),
            report=FinalReportGQL.from_domain(turn.report),
        )


@strawberry.type
class ConversationGQL:
    id: strawberry.ID
    created_at: str
    updated_at: str
    turns: list[ConversationTurnGQL]

    @classmethod
    def from_domain(cls, conversation: Conversation) -> ConversationGQL:
        return cls(
            id=strawberry.ID(conversation.id),
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            turns=[ConversationTurnGQL.from_domain(t) for t in conversation.turns],
        )


@strawberry.type
class ProgressEventGQL:
    stage: str
    message: str
    attempt: int
    payload_json: str

    @classmethod
    def from_domain(cls, evt: ProgressEvent) -> ProgressEventGQL:
        return cls(
            stage=evt.stage,
            message=evt.message,
            attempt=evt.attempt,
            payload_json=json.dumps(evt.payload, ensure_ascii=False, default=str),
        )


@strawberry.type
class RejectedEventGQL:
    reason: str

    @classmethod
    def from_domain(cls, evt: RejectedEvent) -> RejectedEventGQL:
        return cls(reason=evt.reason)


@strawberry.type
class FailedEventGQL:
    stage: str
    error: str

    @classmethod
    def from_domain(cls, evt: FailedEvent) -> FailedEventGQL:
        return cls(stage=evt.stage, error=evt.error)


@strawberry.type
class ResultEventGQL:
    report: FinalReportGQL

    @classmethod
    def from_domain(cls, report: FinalReport) -> ResultEventGQL:
        return cls(report=FinalReportGQL.from_domain(report))


PipelineEventGQL = Annotated[
    ProgressEventGQL | RejectedEventGQL | FailedEventGQL | ResultEventGQL,
    strawberry.union("PipelineEvent"),
]


def progress_event_to_graphql(
    evt: PipelineEvent,
) -> ProgressEventGQL | RejectedEventGQL | FailedEventGQL:
    """Map a domain event (other than RESULT) to its GraphQL type.

    RESULT events are mapped separately in the Subscription resolver because they
    need to fetch the report from the SessionManager.
    """
    if evt.type == PipelineEventType.PROGRESS:
        assert isinstance(evt, ProgressEvent)
        return ProgressEventGQL.from_domain(evt)
    if evt.type == PipelineEventType.REJECTED:
        assert isinstance(evt, RejectedEvent)
        return RejectedEventGQL.from_domain(evt)
    if evt.type == PipelineEventType.FAILED:
        assert isinstance(evt, FailedEvent)
        return FailedEventGQL.from_domain(evt)
    raise ValueError(f"progress_event_to_graphql cannot handle: {evt.type}")
