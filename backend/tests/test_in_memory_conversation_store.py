from __future__ import annotations

import pytest

from app.adapters.conversation.in_memory_store import InMemoryConversationStore
from app.domain.conversation import ConversationTurn
from app.domain.models import (
    AnalysisResult,
    ChartSpec,
    FinalReport,
    QueryResult,
    Question,
    SQLQuery,
)


def _make_turn(question_text: str = "q") -> ConversationTurn:
    return ConversationTurn(
        report=FinalReport(
            question=Question(text=question_text),
            sql=SQLQuery(sql="SELECT 1"),
            result=QueryResult(columns=("x",), rows=((1,),), row_count=1),
            analysis=AnalysisResult(
                summary="s",
                chart=ChartSpec(type="table", x=None, y=None, title="t"),
            ),
        )
    )


async def test_create_returns_empty_conversation_with_unique_id() -> None:
    store = InMemoryConversationStore()
    c1 = await store.create()
    c2 = await store.create()
    assert c1.id != c2.id
    assert c1.turns == ()
    assert c1.created_at == c1.updated_at


async def test_get_returns_none_for_unknown_id() -> None:
    store = InMemoryConversationStore()
    assert (await store.get("nope")) is None


async def test_append_turn_persists_and_returns_updated() -> None:
    store = InMemoryConversationStore()
    created = await store.create()
    turn = _make_turn("first")

    updated = await store.append_turn(created.id, turn)

    assert updated is not None
    assert len(updated.turns) == 1
    assert updated.turns[0].report.question.text == "first"
    assert updated.updated_at >= created.created_at

    fetched = await store.get(created.id)
    assert fetched is not None
    assert len(fetched.turns) == 1


async def test_append_turn_unknown_id_returns_none() -> None:
    store = InMemoryConversationStore()
    assert (await store.append_turn("doesnotexist", _make_turn())) is None


async def test_per_conversation_turn_cap_drops_oldest() -> None:
    store = InMemoryConversationStore(max_turns_per_conversation=2)
    convo = await store.create()
    await store.append_turn(convo.id, _make_turn("a"))
    await store.append_turn(convo.id, _make_turn("b"))
    final = await store.append_turn(convo.id, _make_turn("c"))

    assert final is not None
    assert [t.report.question.text for t in final.turns] == ["b", "c"]


async def test_lru_eviction_drops_oldest_conversation() -> None:
    store = InMemoryConversationStore(max_conversations=2)
    c1 = await store.create()
    c2 = await store.create()
    c3 = await store.create()  # should evict c1

    assert (await store.get(c1.id)) is None
    assert (await store.get(c2.id)) is not None
    assert (await store.get(c3.id)) is not None


async def test_lru_keeps_recently_accessed() -> None:
    store = InMemoryConversationStore(max_conversations=2)
    c1 = await store.create()
    c2 = await store.create()

    # Touch c1 → c1 becomes most-recent, c2 becomes oldest
    await store.get(c1.id)

    c3 = await store.create()  # should evict c2, not c1

    assert (await store.get(c2.id)) is None
    assert (await store.get(c1.id)) is not None
    assert (await store.get(c3.id)) is not None


async def test_invalid_capacities_rejected() -> None:
    with pytest.raises(ValueError):
        InMemoryConversationStore(max_conversations=0)
    with pytest.raises(ValueError):
        InMemoryConversationStore(max_turns_per_conversation=0)
