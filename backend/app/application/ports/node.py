from __future__ import annotations

from typing import Protocol

from app.application.pipeline.state import PipelineState


class Node(Protocol):
    name: str

    async def run(self, state: PipelineState) -> PipelineState: ...
