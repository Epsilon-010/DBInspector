"""End-to-end orchestrator scenarios with fakes — the four critical paths of the graph."""
from __future__ import annotations

import asyncio

from app.adapters.event_bus.asyncio_bus import AsyncioEventBus
from app.application.pipeline.nodes.analyzer import AnalyzerNode
from app.application.pipeline.nodes.guardrail import GuardrailNode
from app.application.pipeline.nodes.sql_executor import SQLExecutorNode
from app.application.pipeline.nodes.sql_generator import SQLGeneratorNode
from app.application.pipeline.orchestrator import PipelineNodes, PipelineOrchestrator
from app.application.pipeline.state import PipelineState
from app.domain.conversation import ConversationTurn
from app.domain.events import PipelineEventType
from app.domain.models import (
    AnalysisResult,
    ChartSpec,
    FinalReport,
    QueryResult,
    Question,
    SQLQuery,
)

from tests.conftest import FakeDatabase, FakeIntrospector, FakeLLM, FakeValidator


class _FakeProcessor:
    """Skip Pandas — DataProcessor's own tests cover its behavior."""

    name = "data_processor"

    async def run(self, state: PipelineState) -> PipelineState:
        rows = state.result.to_dict_rows() if state.result else []
        return state.with_(processed_rows=rows)


def _build(
    *,
    llm: FakeLLM | None = None,
    db: FakeDatabase | None = None,
    bus: AsyncioEventBus | None = None,
    max_retries: int = 2,
) -> tuple[PipelineOrchestrator, AsyncioEventBus, FakeDatabase]:
    llm = llm or FakeLLM()
    db = db or FakeDatabase()
    bus = bus or AsyncioEventBus()
    nodes = PipelineNodes(
        guardrail=GuardrailNode(llm),
        sql_generator=SQLGeneratorNode(llm, FakeIntrospector()),
        sql_executor=SQLExecutorNode(db, FakeValidator(), timeout_seconds=5, max_rows=100),
        data_processor=_FakeProcessor(),  # type: ignore[arg-type]
        analyzer=AnalyzerNode(llm),
    )
    orchestrator = PipelineOrchestrator(nodes=nodes, event_bus=bus, max_sql_retries=max_retries)
    return orchestrator, bus, db


async def _drive(orch: PipelineOrchestrator, bus: AsyncioEventBus, q: str):
    consumer = asyncio.create_task(_collect(bus))
    report = await orch.run(Question(text=q))
    return report, await consumer


async def _collect(bus: AsyncioEventBus) -> list:
    return [evt async for evt in bus.stream()]


def _progress_stages(events: list) -> list[str]:
    return [e.stage for e in events if e.type == PipelineEventType.PROGRESS]


def _progress_attempts(events: list, stage: str) -> list[int]:
    return [
        e.attempt
        for e in events
        if e.type == PipelineEventType.PROGRESS and e.stage == stage
    ]


async def test_happy_path_runs_all_nodes_in_order() -> None:
    orch, bus, _ = _build()
    report, events = await _drive(orch, bus, "¿top productos?")
    assert report is not None
    assert _progress_stages(events) == [
        "guardrail",
        "sql_generator",
        "sql_executor",
        "data_processor",
        "analyzer",
    ]
    assert any(e.type == PipelineEventType.RESULT for e in events)


async def test_guardrail_rejection_short_circuits() -> None:
    orch, bus, _ = _build(llm=FakeLLM(guardrail_safe=False, guardrail_reason="no"))
    report, events = await _drive(orch, bus, "DROP everything")
    assert report is None
    assert any(e.type == PipelineEventType.REJECTED for e in events)
    assert _progress_stages(events) == ["guardrail"]


async def test_sql_retry_recovers_on_second_attempt() -> None:
    db = FakeDatabase(fail_count=1)
    orch, bus, _ = _build(db=db, max_retries=2)
    report, events = await _drive(orch, bus, "¿top productos?")
    assert report is not None
    assert _progress_attempts(events, "sql_generator") == [1, 2]
    assert db.calls == 2


async def test_sql_retry_exhaustion_emits_failed_event() -> None:
    db = FakeDatabase(fail_count=99)
    orch, bus, _ = _build(db=db, max_retries=2)
    report, events = await _drive(orch, bus, "¿top productos?")
    assert report is None
    assert any(e.type == PipelineEventType.FAILED for e in events)
    assert _progress_attempts(events, "sql_generator") == [1, 2, 3]


class _ExplodingLLM:
    """LLM that crashes on any call — simulates network/API failures (timeouts, 500s)."""

    async def complete(self, **_: object) -> str:
        raise RuntimeError("anthropic api unreachable")

    async def complete_json(self, **_: object) -> dict:
        raise RuntimeError("anthropic api unreachable")


async def test_unexpected_exception_emits_failed_event_does_not_leak() -> None:
    """Bug #2 regression: non-PipelineError exceptions must NOT escape orch.run()."""
    orch, bus, _ = _build(llm=_ExplodingLLM())  # type: ignore[arg-type]
    report, events = await _drive(orch, bus, "anything")
    assert report is None
    failed = [e for e in events if e.type == PipelineEventType.FAILED]
    assert len(failed) == 1
    assert "RuntimeError" in failed[0].error
    assert "anthropic api unreachable" in failed[0].error


def _prior_turn(question_text: str, sql: str, summary: str) -> ConversationTurn:
    return ConversationTurn(
        report=FinalReport(
            question=Question(text=question_text),
            sql=SQLQuery(sql=sql),
            result=QueryResult(columns=("x",), rows=((1,),), row_count=1),
            analysis=AnalysisResult(
                summary=summary,
                chart=ChartSpec(type="table", x=None, y=None, title="t"),
            ),
        )
    )


async def test_run_with_history_injects_prior_turns_into_prompts() -> None:
    """When history is passed, the SQL generator + analyzer prompts must contain the
    previous question, SQL, and summary so the LLM can answer follow-ups in context."""
    llm = FakeLLM()
    orch, bus, _ = _build(llm=llm)
    history = (
        _prior_turn(
            question_text="top 5 artistas por ingresos",
            sql="SELECT artist, SUM(total) AS revenue FROM invoices GROUP BY artist LIMIT 5",
            summary="Iron Maiden lidera con $138.60 en ventas totales.",
        ),
    )

    consumer = asyncio.create_task(_collect(bus))
    report = await orch.run(Question(text="ahora desglósalo por país"), history=history)
    await consumer

    assert report is not None

    sql_prompts = [c["user"] for c in llm.complete_calls]
    analyzer_prompts = [c["user"] for c in llm.complete_json_calls if "guardrail" not in c["system"].lower()]
    assert sql_prompts and "Iron Maiden" in sql_prompts[0]
    assert sql_prompts[0].count("top 5 artistas por ingresos") >= 1
    assert analyzer_prompts and "Iron Maiden" in analyzer_prompts[0]


async def test_run_without_history_omits_history_block() -> None:
    """Without history, prompts must not contain the 'Previous conversation' marker."""
    llm = FakeLLM()
    orch, bus, _ = _build(llm=llm)

    consumer = asyncio.create_task(_collect(bus))
    await orch.run(Question(text="¿top productos?"))
    await consumer

    sql_prompt = llm.complete_calls[0]["user"]
    assert "Previous conversation" not in sql_prompt
