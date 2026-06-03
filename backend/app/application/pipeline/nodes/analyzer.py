from __future__ import annotations

import json
from typing import get_args

from app.application.pipeline.state import PipelineState
from app.application.ports.llm import LLMClient
from app.application.prompts.analysis import ANALYSIS_SYSTEM, build_analysis_user
from app.application.prompts.history import take_recent
from app.domain.models import AnalysisResult, ChartSpec, ChartType

_VALID_CHART_TYPES: frozenset[str] = frozenset(get_args(ChartType))


class AnalyzerNode:
    name = "analyzer"

    SAMPLE_SIZE = 20

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(self, state: PipelineState) -> PipelineState:
        if state.result is None or state.sql is None:
            raise RuntimeError("AnalyzerNode invoked without a result/SQL")

        sample = state.processed_rows[: self.SAMPLE_SIZE]
        history = take_recent(state.history)
        payload = await self._llm.complete_json(
            system=ANALYSIS_SYSTEM,
            user=build_analysis_user(
                question=state.question.text,
                sql=state.sql.sql,
                columns=list(state.result.columns),
                row_count=state.result.row_count,
                sample_rows=json.dumps(sample, ensure_ascii=False, default=str),
                sample_size=len(sample),
                history=history,
            ),
            max_tokens=1000,
        )

        chart_payload = payload.get("chart") or {}
        raw_type = str(chart_payload.get("type", "table")).strip().lower()
        chart_type: ChartType = raw_type if raw_type in _VALID_CHART_TYPES else "table"  # type: ignore[assignment]
        analysis = AnalysisResult(
            summary=str(payload.get("summary", "")).strip(),
            chart=ChartSpec(
                type=chart_type,
                x=chart_payload.get("x"),
                y=chart_payload.get("y"),
                series=chart_payload.get("series"),
                title=str(chart_payload.get("title", "")).strip() or "Resultados",
            ),
        )
        return state.with_(analysis=analysis)
