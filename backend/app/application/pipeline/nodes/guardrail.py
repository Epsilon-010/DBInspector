from __future__ import annotations

from app.application.pipeline.state import PipelineState
from app.application.ports.llm import LLMClient
from app.application.prompts.guardrail import GUARDRAIL_SYSTEM, build_guardrail_user
from app.domain.models import GuardrailVerdict


class GuardrailNode:
    name = "guardrail"

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(self, state: PipelineState) -> PipelineState:
        payload = await self._llm.complete_json(
            system=GUARDRAIL_SYSTEM,
            user=build_guardrail_user(state.question.text),
            max_tokens=200,
        )
        verdict = GuardrailVerdict(
            is_safe=bool(payload.get("is_safe", False)),
            reason=str(payload.get("reason", "")),
        )
        return state.with_(verdict=verdict)
