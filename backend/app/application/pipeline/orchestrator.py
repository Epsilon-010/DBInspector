from __future__ import annotations

import logging
import time
from dataclasses import dataclass, fields

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.application.pipeline.nodes.analyzer import AnalyzerNode
from app.application.pipeline.nodes.data_processor import DataProcessorNode
from app.application.pipeline.nodes.guardrail import GuardrailNode
from app.application.pipeline.nodes.sql_executor import SQLExecutorNode
from app.application.pipeline.nodes.sql_generator import SQLGeneratorNode
from app.application.pipeline.state import PipelineState
from app.application.ports.event_bus import EventBus
from app.domain.conversation import ConversationTurn
from app.domain.errors import (
    PipelineError,
    QueryExecutionError,
    UnsafeQueryError,
)
from app.domain.events import FailedEvent, ProgressEvent, RejectedEvent, ResultEvent
from app.domain.models import FinalReport, Question

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineNodes:
    guardrail: GuardrailNode
    sql_generator: SQLGeneratorNode
    sql_executor: SQLExecutorNode
    data_processor: DataProcessorNode
    analyzer: AnalyzerNode


_ROUTE_NEXT = "next"
_ROUTE_RETRY = "retry"
_ROUTE_END = "end"


class PipelineOrchestrator:
    def __init__(
        self,
        nodes: PipelineNodes,
        event_bus: EventBus,
        *,
        max_sql_retries: int,
    ) -> None:
        self._nodes = nodes
        self._bus = event_bus
        self._max_attempts = max_sql_retries + 1
        self._graph = self._build_graph()

    def _build_graph(self):
        guardrail = self._nodes.guardrail.name
        sql_generator = self._nodes.sql_generator.name
        sql_executor = self._nodes.sql_executor.name
        data_processor = self._nodes.data_processor.name
        analyzer = self._nodes.analyzer.name

        sg: StateGraph = StateGraph(PipelineState)
        sg.add_node(guardrail, self._guardrail_step)
        sg.add_node(sql_generator, self._sql_generator_step)
        sg.add_node(sql_executor, self._sql_executor_step)
        sg.add_node(data_processor, self._data_processor_step)
        sg.add_node(analyzer, self._analyzer_step)

        sg.add_edge(START, guardrail)
        sg.add_conditional_edges(
            guardrail,
            self._route_after_guardrail,
            {_ROUTE_NEXT: sql_generator, _ROUTE_END: END},
        )
        sg.add_edge(sql_generator, sql_executor)
        sg.add_conditional_edges(
            sql_executor,
            self._route_after_executor,
            {_ROUTE_NEXT: data_processor, _ROUTE_RETRY: sql_generator, _ROUTE_END: END},
        )
        sg.add_edge(data_processor, analyzer)
        sg.add_edge(analyzer, END)
        return sg.compile()

    async def _guardrail_step(self, state: PipelineState) -> PipelineState:
        await self._bus.publish(
            ProgressEvent(stage=self._nodes.guardrail.name, message="Validando seguridad…")
        )
        return await self._nodes.guardrail.run(state)

    async def _sql_generator_step(self, state: PipelineState) -> PipelineState:
        attempt = state.sql_attempt + 1
        message = "Generando SQL…" if attempt == 1 else "Corrigiendo SQL…"
        await self._bus.publish(
            ProgressEvent(stage=self._nodes.sql_generator.name, message=message, attempt=attempt)
        )
        return await self._nodes.sql_generator.run(state)

    async def _sql_executor_step(self, state: PipelineState) -> PipelineState:
        await self._bus.publish(
            ProgressEvent(
                stage=self._nodes.sql_executor.name,
                message="Ejecutando consulta…",
                attempt=state.sql_attempt,
                payload={"sql": state.sql.sql if state.sql else ""},
            )
        )
        try:
            return await self._nodes.sql_executor.run(state)
        except UnsafeQueryError as exc:
            return state.with_(last_sql_error=f"SQL rechazado por validador: {exc}")
        except QueryExecutionError as exc:
            return state.with_(last_sql_error=str(exc))

    async def _data_processor_step(self, state: PipelineState) -> PipelineState:
        await self._bus.publish(
            ProgressEvent(stage=self._nodes.data_processor.name, message="Procesando datos…")
        )
        return await self._nodes.data_processor.run(state)

    async def _analyzer_step(self, state: PipelineState) -> PipelineState:
        await self._bus.publish(
            ProgressEvent(stage=self._nodes.analyzer.name, message="Analizando resultados…")
        )
        return await self._nodes.analyzer.run(state)

    def _route_after_guardrail(self, state: PipelineState) -> str:
        if state.verdict is not None and state.verdict.is_safe:
            return _ROUTE_NEXT
        return _ROUTE_END

    def _route_after_executor(self, state: PipelineState) -> str:
        if state.last_sql_error is None:
            return _ROUTE_NEXT
        if state.sql_attempt >= self._max_attempts:
            return _ROUTE_END
        return _ROUTE_RETRY

    async def run(
        self,
        question: Question,
        *,
        history: tuple[ConversationTurn, ...] = (),
    ) -> FinalReport | None:
        initial = PipelineState(question=question, history=history)
        started_at = time.perf_counter()
        outcome: str = "ok"
        try:
            raw_final = await self._graph.ainvoke(initial)
            state = _coerce_state(raw_final)

            if state.verdict is not None and not state.verdict.is_safe:
                outcome = "rejected"
                await self._bus.publish(RejectedEvent(reason=state.verdict.reason))
                return None

            if state.last_sql_error is not None and state.result is None:
                outcome = "sql_failed"
                await self._bus.publish(
                    FailedEvent(
                        stage="pipeline",
                        error=(
                            f"SQL falló tras {self._max_attempts} intentos: "
                            f"{state.last_sql_error}"
                        ),
                    )
                )
                return None

            report = self._build_report(state)
            await self._bus.publish(ResultEvent(report=report.model_dump(mode="json")))
            return report

        except PipelineError as exc:
            outcome = "pipeline_error"
            await self._bus.publish(FailedEvent(stage="pipeline", error=str(exc)))
            return None
        except Exception as exc:  # noqa: BLE001 - last-ditch catch so the subscription sees a final event
            outcome = "unexpected_error"
            _log.exception("pipeline_unexpected_error")
            await self._bus.publish(
                FailedEvent(stage="pipeline", error=f"{type(exc).__name__}: {exc}")
            )
            return None
        finally:
            await self._bus.close()
            _log.info(
                "pipeline_completed",
                extra={
                    "outcome": outcome,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
                },
            )

    @staticmethod
    def _build_report(state: PipelineState) -> FinalReport:
        if state.sql is None or state.result is None or state.analysis is None:
            raise PipelineError("Estado del pipeline incompleto al construir reporte final.")
        return FinalReport(
            question=state.question,
            sql=state.sql,
            result=state.result,
            analysis=state.analysis,
        )


_PIPELINE_STATE_FIELDS = frozenset(f.name for f in fields(PipelineState))


def _coerce_state(raw) -> PipelineState:
    # LangGraph returns either the dataclass or an AddableValuesDict depending on version.
    if isinstance(raw, PipelineState):
        return raw
    if isinstance(raw, dict):
        kwargs = {k: v for k, v in raw.items() if k in _PIPELINE_STATE_FIELDS}
        return PipelineState(**kwargs)
    raise TypeError(f"Unexpected state type returned by LangGraph: {type(raw).__name__}")
