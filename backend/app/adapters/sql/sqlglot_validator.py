from __future__ import annotations

import sqlglot
from sqlglot import exp

from app.domain.errors import UnsafeQueryError
from app.domain.models import SQLQuery

_FORBIDDEN_NODE_NAMES: frozenset[str] = frozenset(
    {
        "Insert",
        "Update",
        "Delete",
        "Drop",
        "AlterTable",
        "Alter",
        "Create",
        "TruncateTable",
        "Truncate",
        "Merge",
        "Command",
        "Grant",
        "Revoke",
    }
)


def _resolve_forbidden_classes() -> tuple[type[exp.Expression], ...]:
    found: list[type[exp.Expression]] = []
    for name in _FORBIDDEN_NODE_NAMES:
        cls = getattr(exp, name, None)
        if isinstance(cls, type) and issubclass(cls, exp.Expression):
            found.append(cls)
    return tuple(found)


_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = _resolve_forbidden_classes()


class SqlglotValidator:
    def __init__(self, dialect: str = "postgres") -> None:
        self._dialect = dialect

    def validate(self, query: SQLQuery) -> None:
        try:
            statements = sqlglot.parse(query.sql, read=self._dialect)
        except sqlglot.errors.ParseError as exc:
            raise UnsafeQueryError(f"SQL no parseable: {exc}") from exc

        non_empty = [s for s in statements if s is not None]
        if len(non_empty) != 1:
            raise UnsafeQueryError(
                f"Solo se permite una sentencia, recibí {len(non_empty)}."
            )

        root = non_empty[0]
        if root.find(exp.Select) is None:
            raise UnsafeQueryError("Solo se permiten consultas SELECT.")

        for forbidden in _FORBIDDEN_NODES:
            if root.find(forbidden) is not None:
                raise UnsafeQueryError(
                    f"Operación prohibida detectada: {forbidden.__name__}."
                )
