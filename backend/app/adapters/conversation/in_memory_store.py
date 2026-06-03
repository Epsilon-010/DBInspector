from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict

from app.application.ports.conversation_store import ConversationStore
from app.domain.conversation import Conversation, ConversationTurn


class InMemoryConversationStore(ConversationStore):
    def __init__(
        self,
        *,
        max_conversations: int = 50,
        max_turns_per_conversation: int = 20,
    ) -> None:
        if max_conversations <= 0:
            raise ValueError("max_conversations must be positive")
        if max_turns_per_conversation <= 0:
            raise ValueError("max_turns_per_conversation must be positive")
        self._conversations: OrderedDict[str, Conversation] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_conversations = max_conversations
        self._max_turns = max_turns_per_conversation

    async def create(self) -> Conversation:
        conversation = Conversation(id=uuid.uuid4().hex)
        async with self._lock:
            self._conversations[conversation.id] = conversation
            self._evict_if_over_cap()
        return conversation

    async def get(self, conversation_id: str) -> Conversation | None:
        async with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is not None:
                self._conversations.move_to_end(conversation_id)
            return conversation

    async def append_turn(
        self, conversation_id: str, turn: ConversationTurn
    ) -> Conversation | None:
        async with self._lock:
            current = self._conversations.get(conversation_id)
            if current is None:
                return None
            updated = current.with_turn(turn, max_turns=self._max_turns)
            self._conversations[conversation_id] = updated
            self._conversations.move_to_end(conversation_id)
            return updated

    def _evict_if_over_cap(self) -> None:
        while len(self._conversations) > self._max_conversations:
            self._conversations.popitem(last=False)
