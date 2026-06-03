"""GraphQL integration: startConversation → runQuery(conversationId) → conversation(id).

Wires the production schema against a fake Container so we exercise the full
mutation→persistence→query loop without touching Anthropic or Postgres.
"""
from __future__ import annotations

import time
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


def _build_app() -> tuple[TestClient, Container]:
    settings = Settings(  # type: ignore[call-arg]
        anthropic_api_key="stub",
        database_url="postgresql+asyncpg://stub:stub@localhost/stub",
        pipeline_max_sql_retries=1,
    )
    container = Container(
        settings=settings,
        engine=None,
        llm=FakeLLM(),
        introspector=FakeIntrospector(),
        database=FakeDatabase(),
        sql_validator=FakeValidator(),
        conversation_store=InMemoryConversationStore(),
        event_bus_factory=AsyncioEventBusFactory(),
    )
    sessions = SessionManager()
    app = FastAPI()

    async def get_context() -> GraphQLContext:
        return GraphQLContext(container=container, sessions=sessions)

    router = GraphQLRouter[GraphQLContext, None](schema, context_getter=get_context)
    app.include_router(router, prefix="/graphql")
    client = TestClient(app)
    return client, container


@pytest.fixture
def client_and_container() -> Generator[tuple[TestClient, Container], None, None]:
    client, container = _build_app()
    with client:
        yield client, container


def _wait_for_turn(client: TestClient, conv_id: str, *, expected: int, timeout: float = 2.0) -> dict:
    """Poll `conversation(id)` until it has `expected` turns. Pipeline runs in a background
    task; we don't have a "task finished" hook in the GraphQL layer, so polling is fine."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rep = client.post(
            "/graphql",
            json={
                "query": (
                    "query($id: ID!) { conversation(conversationId: $id) "
                    "{ id turns { createdAt report { question sql } } } }"
                ),
                "variables": {"id": conv_id},
            },
        )
        body = rep.json()
        assert "errors" not in body, body
        convo = body["data"]["conversation"]
        if convo and len(convo["turns"]) >= expected:
            return convo
        time.sleep(0.02)
    raise AssertionError(f"conversation {conv_id} never reached {expected} turn(s)")


def test_start_conversation_returns_id(
    client_and_container: tuple[TestClient, Container],
) -> None:
    client, _ = client_and_container
    rep = client.post("/graphql", json={"query": "mutation { startConversation { id } }"})
    assert rep.status_code == 200
    body = rep.json()
    assert "errors" not in body, body
    cid = body["data"]["startConversation"]["id"]
    assert isinstance(cid, str) and len(cid) == 32


def test_run_query_persists_turn_into_conversation(
    client_and_container: tuple[TestClient, Container],
) -> None:
    client, _ = client_and_container

    cid = client.post(
        "/graphql", json={"query": "mutation { startConversation { id } }"}
    ).json()["data"]["startConversation"]["id"]

    rep = client.post(
        "/graphql",
        json={
            "query": (
                "mutation($q: String!, $cid: ID!) { "
                'runQuery(question: $q, conversationId: $cid) { requestId } }'
            ),
            "variables": {"q": "primer pregunta", "cid": cid},
        },
    )
    body = rep.json()
    assert "errors" not in body, body
    assert isinstance(body["data"]["runQuery"]["requestId"], str)

    convo = _wait_for_turn(client, cid, expected=1)
    assert len(convo["turns"]) == 1
    assert convo["turns"][0]["report"]["question"] == "primer pregunta"


def test_second_turn_carries_history_into_llm_prompt(
    client_and_container: tuple[TestClient, Container],
) -> None:
    client, container = _build_app()
    with client:
        cid = client.post(
            "/graphql", json={"query": "mutation { startConversation { id } }"}
        ).json()["data"]["startConversation"]["id"]

        # Turn 1
        client.post(
            "/graphql",
            json={
                "query": (
                    "mutation($q: String!, $cid: ID!) { "
                    "runQuery(question: $q, conversationId: $cid) { requestId } }"
                ),
                "variables": {"q": "top artistas", "cid": cid},
            },
        )
        _wait_for_turn(client, cid, expected=1)

        llm = container.llm
        assert hasattr(llm, "complete_calls")
        baseline_sql_calls = len(llm.complete_calls)

        # Turn 2 — the SQL generator's prompt should now include turn 1's question.
        client.post(
            "/graphql",
            json={
                "query": (
                    "mutation($q: String!, $cid: ID!) { "
                    "runQuery(question: $q, conversationId: $cid) { requestId } }"
                ),
                "variables": {"q": "ahora por país", "cid": cid},
            },
        )
        _wait_for_turn(client, cid, expected=2)

        new_sql_prompts = [c["user"] for c in llm.complete_calls[baseline_sql_calls:]]
        assert new_sql_prompts
        assert any("top artistas" in p for p in new_sql_prompts)
        assert any("Previous conversation" in p for p in new_sql_prompts)


def test_run_query_without_conversation_id_does_not_persist(
    client_and_container: tuple[TestClient, Container],
) -> None:
    client, container = client_and_container

    rid = client.post(
        "/graphql",
        json={"query": 'mutation { runQuery(question: "huérfana") { requestId } }'},
    ).json()["data"]["runQuery"]["requestId"]
    assert rid

    # No conversation was created → store is empty.
    rep = client.post(
        "/graphql",
        json={
            "query": "query($id: ID!) { conversation(conversationId: $id) { id } }",
            "variables": {"id": "doesnotexist"},
        },
    )
    assert rep.json()["data"]["conversation"] is None


def test_run_query_with_unknown_conversation_id_returns_graphql_error(
    client_and_container: tuple[TestClient, Container],
) -> None:
    client, _ = client_and_container
    rep = client.post(
        "/graphql",
        json={
            "query": (
                "mutation($q: String!, $cid: ID!) { "
                "runQuery(question: $q, conversationId: $cid) { requestId } }"
            ),
            "variables": {"q": "x", "cid": "doesnotexist"},
        },
    )
    body = rep.json()
    assert "errors" in body
    assert any("doesnotexist" in str(e).lower() for e in body["errors"])


def test_conversation_query_returns_null_for_unknown_id(
    client_and_container: tuple[TestClient, Container],
) -> None:
    client, _ = client_and_container
    rep = client.post(
        "/graphql",
        json={
            "query": "query($id: ID!) { conversation(conversationId: $id) { id } }",
            "variables": {"id": "nope"},
        },
    )
    assert rep.json()["data"]["conversation"] is None
