from __future__ import annotations

from collections.abc import Sequence

from app.domain.conversation import ConversationTurn

MAX_HISTORY_TURNS_IN_PROMPT = 5


def take_recent(turns: Sequence[ConversationTurn]) -> tuple[ConversationTurn, ...]:
    if not turns:
        return ()
    return tuple(turns[-MAX_HISTORY_TURNS_IN_PROMPT:])


def render_history_block(turns: Sequence[ConversationTurn]) -> str:
    if not turns:
        return ""

    lines: list[str] = [
        "",
        "Previous conversation (oldest → newest, treat as context for follow-up questions):",
    ]
    for idx, turn in enumerate(turns, start=1):
        report = turn.report
        lines.append(f"[{idx}] Question: {report.question.text}")
        lines.append(f"    SQL: {_collapse(report.sql.sql)}")
        lines.append(f"    Rows returned: {report.result.row_count}")
        lines.append(f"    Summary: {_collapse(report.analysis.summary)}")
    lines.append("")
    return "\n".join(lines)


def _collapse(text: str, *, max_chars: int = 400) -> str:
    flat = " ".join(text.split())
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - 1].rstrip() + "…"
