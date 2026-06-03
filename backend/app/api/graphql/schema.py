from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import strawberry
from strawberry.fastapi import BaseContext
from strawberry.types import Info

from app.api.graphql.types import (
    ConversationGQL,
    ConversationHandleGQL,
    FailedEventGQL,
    FinalReportGQL,
    PipelineEventGQL,
    ResultEventGQL,
    RunQueryHandle,
    progress_event_to_graphql,
)
from app.api.session_manager import SessionManager
from app.application.pipeline.orchestrator import PipelineOrchestrator
from app.application.ports.conversation_store import ConversationStore
from app.composition import Container
from app.domain.conversation import ConversationTurn
from app.domain.events import PipelineEventType
from app.domain.models import FinalReport, Question
from app.observability import bind_request_id

_log = logging.getLogger(__name__)


class GraphQLContext(BaseContext):
    def __init__(self, container: Container, sessions: SessionManager) -> None:
        super().__init__()
        self.container = container
        self.sessions = sessions


@strawberry.type
class Query:
    @strawberry.field
    async def report(self, info: Info, request_id: strawberry.ID) -> FinalReportGQL | None:
        ctx: GraphQLContext = info.context
        report = await ctx.sessions.get_report(str(request_id))
        return FinalReportGQL.from_domain(report) if report else None

    @strawberry.field
    async def conversation(
        self, info: Info, conversation_id: strawberry.ID
    ) -> ConversationGQL | None:
        ctx: GraphQLContext = info.context
        conversation = await ctx.container.conversation_store.get(str(conversation_id))
        return ConversationGQL.from_domain(conversation) if conversation else None

    @strawberry.field
    def health(self) -> str:
        return "ok"


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def start_conversation(self, info: Info) -> ConversationHandleGQL:
        ctx: GraphQLContext = info.context
        conversation = await ctx.container.conversation_store.create()
        return ConversationHandleGQL(id=strawberry.ID(conversation.id))

    @strawberry.mutation
    async def run_query(
        self,
        info: Info,
        question: str,
        conversation_id: strawberry.ID | None = None,
    ) -> RunQueryHandle:
        ctx: GraphQLContext = info.context

        history: tuple[ConversationTurn, ...] = ()
        conv_id_str: str | None = None
        if conversation_id is not None:
            conv_id_str = str(conversation_id)
            conversation = await ctx.container.conversation_store.get(conv_id_str)
            if conversation is None:
                raise ValueError(f"unknown conversationId: {conv_id_str}")
            history = conversation.turns

        request_id = SessionManager.next_request_id()
        bus = ctx.container.event_bus_factory.create(request_id)
        orchestrator = ctx.container.make_orchestrator(bus)
        task = asyncio.create_task(
            _run_and_persist(
                orchestrator=orchestrator,
                question=Question(text=question),
                history=history,
                conversation_id=conv_id_str,
                store=ctx.container.conversation_store,
                request_id=request_id,
            )
        )
        await ctx.sessions.register(bus, task, request_id=request_id)
        return RunQueryHandle(request_id=strawberry.ID(request_id))


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def progress(
        self, info: Info, request_id: strawberry.ID
    ) -> AsyncIterator[PipelineEventGQL]:
        ctx: GraphQLContext = info.context
        rid = str(request_id)
        bus = await ctx.sessions.get_bus(rid)
        if bus is None:
            yield FailedEventGQL(stage="session", error=f"unknown requestId: {rid}")
            return

        try:
            async for evt in bus.stream():
                if evt.type == PipelineEventType.RESULT:
                    report = await ctx.sessions.get_report(rid)
                    if report is not None:
                        yield ResultEventGQL.from_domain(report)
                    continue
                yield progress_event_to_graphql(evt)
        finally:
            await ctx.sessions.discard(rid)


async def _run_and_persist(
    *,
    orchestrator: PipelineOrchestrator,
    question: Question,
    history: tuple[ConversationTurn, ...],
    conversation_id: str | None,
    store: ConversationStore,
    request_id: str,
) -> FinalReport | None:
    with bind_request_id(request_id):
        _log.info(
            "pipeline_run_started",
            extra={
                "conversation_id": conversation_id,
                "history_turns": len(history),
                "question_chars": len(question.text),
            },
        )
        report = await orchestrator.run(question, history=history)
        if report is not None and conversation_id is not None:
            await store.append_turn(conversation_id, ConversationTurn(report=report))
        _log.info(
            "pipeline_run_finished",
            extra={
                "success": report is not None,
                "persisted": report is not None and conversation_id is not None,
            },
        )
        return report


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
