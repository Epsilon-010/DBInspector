from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.adapters.conversation.in_memory_store import InMemoryConversationStore
from app.adapters.db.caching_introspector import CachingSchemaIntrospector
from app.adapters.db.executor import PostgresDatabase
from app.adapters.db.introspector import PostgresIntrospector
from app.adapters.demo.demo_adapters import (
    DemoDatabase,
    DemoIntrospector,
    DemoLLMClient,
    DemoSQLValidator,
)
from app.adapters.event_bus.asyncio_bus import AsyncioEventBusFactory
from app.adapters.llm.langchain_client import LangChainLLMClient
from app.adapters.sql.sqlglot_validator import SqlglotValidator
from app.application.pipeline.nodes.analyzer import AnalyzerNode
from app.application.pipeline.nodes.data_processor import DataProcessorNode
from app.application.pipeline.nodes.guardrail import GuardrailNode
from app.application.pipeline.nodes.sql_executor import SQLExecutorNode
from app.application.pipeline.nodes.sql_generator import SQLGeneratorNode
from app.application.pipeline.orchestrator import PipelineNodes, PipelineOrchestrator
from app.application.ports.conversation_store import ConversationStore
from app.application.ports.database import Database, SchemaIntrospector
from app.application.ports.event_bus import EventBus, EventBusFactory
from app.application.ports.llm import LLMClient
from app.application.ports.sql_validator import SQLValidator
from app.config import Settings


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine | None
    llm: LLMClient
    introspector: SchemaIntrospector
    database: Database
    sql_validator: SQLValidator
    conversation_store: ConversationStore
    event_bus_factory: EventBusFactory

    @classmethod
    def build(cls, settings: Settings) -> Container:
        if settings.demo_mode:
            return cls._build_demo(settings)
        engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle_seconds,
            pool_pre_ping=settings.db_pool_pre_ping,
        )
        introspector: SchemaIntrospector = CachingSchemaIntrospector(
            PostgresIntrospector(engine),
            ttl_seconds=settings.pipeline_schema_cache_ttl_seconds,
        )
        return cls(
            settings=settings,
            engine=engine,
            llm=LangChainLLMClient(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            ),
            introspector=introspector,
            database=PostgresDatabase(engine),
            sql_validator=SqlglotValidator(),
            conversation_store=InMemoryConversationStore(),
            event_bus_factory=AsyncioEventBusFactory(),
        )

    @classmethod
    def _build_demo(cls, settings: Settings) -> Container:
        return cls(
            settings=settings,
            engine=None,
            llm=DemoLLMClient(),
            introspector=DemoIntrospector(),
            database=DemoDatabase(),
            sql_validator=DemoSQLValidator(),
            conversation_store=InMemoryConversationStore(),
            event_bus_factory=AsyncioEventBusFactory(),
        )

    def make_orchestrator(self, event_bus: EventBus) -> PipelineOrchestrator:
        nodes = PipelineNodes(
            guardrail=GuardrailNode(self.llm),
            sql_generator=SQLGeneratorNode(self.llm, self.introspector),
            sql_executor=SQLExecutorNode(
                self.database,
                self.sql_validator,
                timeout_seconds=self.settings.pipeline_query_timeout_seconds,
                max_rows=self.settings.pipeline_max_result_rows,
            ),
            data_processor=DataProcessorNode(),
            analyzer=AnalyzerNode(self.llm),
        )
        return PipelineOrchestrator(
            nodes=nodes,
            event_bus=event_bus,
            max_sql_retries=self.settings.pipeline_max_sql_retries,
        )

    async def shutdown(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
