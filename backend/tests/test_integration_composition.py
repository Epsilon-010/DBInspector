"""Composition root smoke test — no real DB connection, no real LLM call."""
from __future__ import annotations

from app.adapters.db.caching_introspector import CachingSchemaIntrospector
from app.adapters.db.executor import PostgresDatabase
from app.adapters.event_bus.asyncio_bus import AsyncioEventBus
from app.adapters.llm.langchain_client import LangChainLLMClient
from app.adapters.sql.sqlglot_validator import SqlglotValidator
from app.application.pipeline.orchestrator import PipelineOrchestrator
from app.composition import Container
from app.config import Settings


def _stub_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "demo_mode": False,
        "anthropic_api_key": "stub",
        "database_url": "postgresql+asyncpg://stub:stub@localhost:5432/stub",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def test_container_build_wires_caching_introspector() -> None:
    """SQLGenerator must read the schema through the caching decorator, not raw Postgres."""
    container = Container.build(_stub_settings())
    try:
        assert isinstance(container.introspector, CachingSchemaIntrospector)
    finally:
        await container.shutdown()


async def test_container_build_uses_langchain_adapter_by_default() -> None:
    """LangChain adapter is the default LLM. ClaudeLLMClient stays available as alternate."""
    container = Container.build(_stub_settings())
    try:
        assert isinstance(container.llm, LangChainLLMClient)
    finally:
        await container.shutdown()


async def test_container_build_wires_postgres_adapter_and_sqlglot_validator() -> None:
    container = Container.build(_stub_settings())
    try:
        assert isinstance(container.database, PostgresDatabase)
        assert isinstance(container.sql_validator, SqlglotValidator)
        assert container.engine is not None
    finally:
        await container.shutdown()


async def test_make_orchestrator_produces_orchestrator_with_all_five_nodes() -> None:
    container = Container.build(_stub_settings())
    try:
        orchestrator = container.make_orchestrator(AsyncioEventBus())
        assert isinstance(orchestrator, PipelineOrchestrator)
        # Internal but worth asserting: all 5 nodes wired with the right names
        names = {
            orchestrator._nodes.guardrail.name,
            orchestrator._nodes.sql_generator.name,
            orchestrator._nodes.sql_executor.name,
            orchestrator._nodes.data_processor.name,
            orchestrator._nodes.analyzer.name,
        }
        assert names == {
            "guardrail",
            "sql_generator",
            "sql_executor",
            "data_processor",
            "analyzer",
        }
    finally:
        await container.shutdown()


async def test_make_orchestrator_threads_settings_to_executor_timeout() -> None:
    container = Container.build(_stub_settings(pipeline_query_timeout_seconds=42))
    try:
        orchestrator = container.make_orchestrator(AsyncioEventBus())
        assert orchestrator._nodes.sql_executor._timeout_seconds == 42
    finally:
        await container.shutdown()


async def test_make_orchestrator_threads_max_retries() -> None:
    container = Container.build(_stub_settings(pipeline_max_sql_retries=5))
    try:
        orchestrator = container.make_orchestrator(AsyncioEventBus())
        # max_attempts = max_retries + 1
        assert orchestrator._max_attempts == 6
    finally:
        await container.shutdown()
