from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

_request_id_var: ContextVar[str | None] = ContextVar("dbinspector_request_id", default=None)


def current_request_id() -> str | None:
    return _request_id_var.get()


@contextmanager
def bind_request_id(request_id: str) -> Generator[None, None, None]:
    token = _request_id_var.set(request_id)
    try:
        yield
    finally:
        _request_id_var.reset(token)
