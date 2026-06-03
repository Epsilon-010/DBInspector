from __future__ import annotations

from app.application.pipeline.state import PipelineState
from app.application.ports.database import SchemaIntrospector
from app.application.ports.llm import LLMClient
from app.application.prompts.history import take_recent
from app.application.prompts.sql_generation import (
    SQL_GEN_SYSTEM,
    build_sql_gen_user,
    build_sql_retry_user,
)
from app.domain.models import SQLQuery


class SQLGeneratorNode:
    name = "sql_generator"

    def __init__(self, llm: LLMClient, introspector: SchemaIntrospector) -> None:
        self._llm = llm
        self._introspector = introspector

    async def run(self, state: PipelineState) -> PipelineState:
        schema = state.schema or await self._introspector.snapshot()
        history = take_recent(state.history)

        if state.last_sql_error and state.sql is not None:
            user_prompt = build_sql_retry_user(
                schema=schema.to_prompt_string(),
                question=state.question.text,
                previous_sql=state.sql.sql,
                error=state.last_sql_error,
                history=history,
            )
        else:
            user_prompt = build_sql_gen_user(
                schema=schema.to_prompt_string(),
                question=state.question.text,
                history=history,
            )

        sql_text = await self._llm.complete(
            system=SQL_GEN_SYSTEM,
            user=user_prompt,
            max_tokens=800,
        )

        return state.with_(
            schema=schema,
            sql=SQLQuery(sql=_strip_fences(sql_text)),
            sql_attempt=state.sql_attempt + 1,
        )


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip().rstrip(";").strip()
