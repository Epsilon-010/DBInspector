from __future__ import annotations

from typing import Protocol

from app.domain.models import SQLQuery


class SQLValidator(Protocol):
    def validate(self, query: SQLQuery) -> None: ...
