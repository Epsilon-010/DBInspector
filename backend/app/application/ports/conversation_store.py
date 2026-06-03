from __future__ import annotations

from typing import Protocol

from app.domain.conversation import Conversation, ConversationTurn


class ConversationStore(Protocol):
    async def create(self) -> Conversation: ...

    async def get(self, conversation_id: str) -> Conversation | None: ...

    async def append_turn(
        self, conversation_id: str, turn: ConversationTurn
    ) -> Conversation | None: ...
