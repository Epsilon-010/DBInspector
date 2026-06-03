from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from app.domain.models import FinalReport, FrozenBase


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConversationTurn(FrozenBase):
    report: FinalReport
    created_at: datetime = Field(default_factory=_utcnow)


class Conversation(FrozenBase):
    id: str = Field(..., min_length=1, max_length=64)
    turns: tuple[ConversationTurn, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def with_turn(self, turn: ConversationTurn, *, max_turns: int) -> Conversation:
        new_turns = (*self.turns, turn)
        if max_turns > 0 and len(new_turns) > max_turns:
            new_turns = new_turns[-max_turns:]
        return self.model_copy(update={"turns": new_turns, "updated_at": _utcnow()})
