"""GraphQL API integration: HTTP layer + Strawberry resolvers + SessionManager + pipeline.

Builds a minimal FastAPI app with the production schema but a Container of fakes — so we
exercise the real Strawberry/HTTP wiring without touching Anthropic or Postgres.
"""
from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from strawberry.fastapi import GraphQLRouter

from app.adapters.conversation.in_memory_store import InMemoryConversationStore
from app.adapters.event_bus.asyncio_bus import AsyncioEventBusFactory
from app.api.graphql.schema import GraphQLContext, schema
from app.api.session_manager import SessionManager
from app.composition import Container
from app.config import Settings

from tests.conftest import FakeDatabase, FakeIntrospector, FakeLLM, FakeValidator


def _build_test_app(container: Container, sessions: SessionManager) -> FastAPI:
    app = FastAPI()

    async def get_context() -> GraphQLContext:
        return GraphQLContext(container=container, sessions=sessions)

    router = GraphQLRouter[GraphQLContext, None](schema, context_getter=get_context)
    app.include_router(router, prefix="/graphql")
    return app


def _build_fake_container(
    llm: FakeLLM | None = None,
    database: FakeDatabase | None = None,
) -> Container:
    settings = Settings(  # type: ignore[call-arg]
        anthropic_api_key="stub",
        database_url="postgresql+asyncpg://stub:stub@localhost/stub",
        pipeline_max_sql_retries=1,
        pipeline_query_timeout_seconds=5,
        pipeline_max_result_rows=100,
    )
    return Container(
        settings=settings,
        engine=None,
        llm=llm or FakeLLM(),
        introspector=FakeIntrospector(),
        database=database or FakeDatabase(),
        sql_validator=FakeValidator(),
        conversation_store=InMemoryConversationStore(),
        event_bus_factory=AsyncioEventBusFactory(),
    )


@pytest.fixture
def client_and_sessions() -> Generator[tuple[TestClient, SessionManager], None, None]:
    sessions = SessionManager()
    container = _build_fake_container()
    app = _build_test_app(container, sessions)
    with TestClient(app) as client:
        yield client, sessions


# ----------------------------- runQuery mutation ----------------------------- #


def test_run_query_returns_request_id(
    client_and_sessions: tuple[TestClient, SessionManager],
) -> None:
    client, _ = client_and_sessions
    response = client.post(
        "/graphql",
        json={
            "query": 'mutation { runQuery(question: "¿top productos?") { requestId } }',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "errors" not in body, body
    request_id = body["data"]["runQuery"]["requestId"]
    assert isinstance(request_id, str)
    assert len(request_id) == 32  # uuid4 hex


def test_run_query_with_missing_argument_returns_graphql_error(
    client_and_sessions: tuple[TestClient, SessionManager],
) -> None:
    client, _ = client_and_sessions
    response = client.post(
        "/graphql",
        json={"query": "mutation { runQuery { requestId } }"},  # missing `question`
    )
    body = response.json()
    assert "errors" in body
    assert any("question" in str(e).lower() for e in body["errors"])


# ----------------------------- report query ----------------------------- #


_REPORT_QUERY = """
query Report($id: ID!) {
  report(requestId: $id) {
    question
    sql
    result { columns rowCount truncated rowsJson }
    analysis { summary chart { type x y title } }
  }
}
"""


def test_report_query_returns_full_report_after_pipeline_completes(
    client_and_sessions: tuple[TestClient, SessionManager],
) -> None:
    client, _ = client_and_sessions

    mut = client.post(
        "/graphql",
        json={"query": 'mutation { runQuery(question: "alpha?") { requestId } }'},
    )
    rid = mut.json()["data"]["runQuery"]["requestId"]

    rep = client.post("/graphql", json={"query": _REPORT_QUERY, "variables": {"id": rid}})
    assert rep.status_code == 200
    body = rep.json()
    assert "errors" not in body, body
    report = body["data"]["report"]
    assert report is not None
    assert report["question"] == "alpha?"
    assert "SELECT" in report["sql"].upper()
    assert report["result"]["columns"] == ["id", "name"]
    assert report["analysis"]["chart"]["type"] in {"bar", "line", "pie", "scatter", "table"}


def test_report_query_unknown_request_id_returns_null(
    client_and_sessions: tuple[TestClient, SessionManager],
) -> None:
    client, _ = client_and_sessions
    rep = client.post(
        "/graphql",
        json={"query": _REPORT_QUERY, "variables": {"id": "doesnotexist"}},
    )
    assert rep.status_code == 200
    assert rep.json()["data"]["report"] is None


# ----------------------------- health ----------------------------- #


def test_health_query_responds() -> None:
    client = TestClient(_build_test_app(_build_fake_container(), SessionManager()))
    rep = client.post("/graphql", json={"query": "{ health }"})
    assert rep.status_code == 200
    assert rep.json()["data"]["health"] == "ok"


# ----------------------------- failure surfaces ----------------------------- #


def test_pipeline_failure_propagates_as_null_report() -> None:
    """When the pipeline crashes (e.g. LLM blows up), the report query returns null and
    the SessionManager records the error string."""

    class _ExplodingLLM:
        async def complete(self, **_: object) -> str:
            raise RuntimeError("upstream LLM 500")

        async def complete_json(self, **_: object) -> dict:
            raise RuntimeError("upstream LLM 500")

    sessions = SessionManager()
    container = _build_fake_container(llm=_ExplodingLLM())  # type: ignore[arg-type]
    app = _build_test_app(container, sessions)

    with TestClient(app) as client:
        mut = client.post(
            "/graphql",
            json={"query": 'mutation { runQuery(question: "x") { requestId } }'},
        )
        rid = mut.json()["data"]["runQuery"]["requestId"]
        rep = client.post(
            "/graphql", json={"query": _REPORT_QUERY, "variables": {"id": rid}}
        )

    assert rep.json()["data"]["report"] is None

    outcome = asyncio.run(sessions.get_outcome(rid))
    assert outcome is not None
    assert outcome.report is None  # pipeline didn't produce a report
    # The orchestrator catches Exception and emits FailedEvent → returns None →
    # outcome.error is None (the task itself didn't raise).
    assert outcome.error is None
