from __future__ import annotations

from collections.abc import Sequence

from app.application.prompts.history import render_history_block
from app.domain.conversation import ConversationTurn

ANALYSIS_SYSTEM = """\
You are a data analyst writing for a non-technical Spanish-speaking executive.

Given the user question, the SQL that answered it, and a sample of the result rows,
produce:
1. `summary`: a concise executive summary in Spanish (2-4 sentences). Cite concrete
   numbers from the data. No fluff, no hedging. If previous conversation context is
   provided, you may reference how this result relates to the prior turn(s).
2. `chart`: a chart specification appropriate for the data shape. Pick `type` from
   "bar", "line", "pie", "scatter", "table". `x` and `y` MUST be column names
   present in the result, or null when not applicable (e.g., "table"). `series` is
   optional, used to break down by category.

Respond with a single JSON object, nothing else, exactly this shape:
{
  "summary": "<spanish summary>",
  "chart": {
    "type": "bar" | "line" | "pie" | "scatter" | "table",
    "x": "<column or null>",
    "y": "<column or null>",
    "series": "<column or null>",
    "title": "<short spanish title>"
  }
}
"""

ANALYSIS_USER_TEMPLATE = """\
User question:
\"\"\"{question}\"\"\"
{history_block}
SQL executed:
{sql}

Result columns: {columns}
Result row count: {row_count}
Sample rows (first {sample_size}):
{sample_rows}
"""


def build_analysis_user(
    *,
    question: str,
    sql: str,
    columns: list[str],
    row_count: int,
    sample_rows: str,
    sample_size: int,
    history: Sequence[ConversationTurn] = (),
) -> str:
    return ANALYSIS_USER_TEMPLATE.format(
        question=question,
        sql=sql,
        columns=columns,
        row_count=row_count,
        sample_size=sample_size,
        sample_rows=sample_rows,
        history_block=render_history_block(history),
    )
