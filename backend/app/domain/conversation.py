from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field, model_validator

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

    @model_validator(mode="before")
    @classmethod
    def _sync_timestamps(cls, data: Any) -> Any:
        if isinstance(data, dict) and "created_at" not in data and "updated_at" not in data:
            now = _utcnow()
            return {**data, "created_at": now, "updated_at": now}
        return data

    def with_turn(self, turn: ConversationTurn, *, max_turns: int) -> Conversation:
        new_turns = (*self.turns, turn)
        if max_turns > 0 and len(new_turns) > max_turns:
            new_turns = new_turns[-max_turns:]
        return self.model_copy(update={"turns": new_turns, "updated_at": _utcnow()})
