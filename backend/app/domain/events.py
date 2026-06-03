from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineEventType(StrEnum):
    PROGRESS = "progress"
    RESULT = "result"
    REJECTED = "rejected"
    FAILED = "failed"


class _BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    type: PipelineEventType


class ProgressEvent(_BaseEvent):
    type: Literal[PipelineEventType.PROGRESS] = PipelineEventType.PROGRESS
    stage: str
    message: str
    attempt: int = 1
    payload: dict[str, Any] = Field(default_factory=dict)


class ResultEvent(_BaseEvent):
    type: Literal[PipelineEventType.RESULT] = PipelineEventType.RESULT
    report: dict[str, Any]


class RejectedEvent(_BaseEvent):
    type: Literal[PipelineEventType.REJECTED] = PipelineEventType.REJECTED
    reason: str


class FailedEvent(_BaseEvent):
    type: Literal[PipelineEventType.FAILED] = PipelineEventType.FAILED
    stage: str
    error: str


PipelineEvent = Annotated[
    ProgressEvent | ResultEvent | RejectedEvent | FailedEvent,
    Field(discriminator="type"),
]
