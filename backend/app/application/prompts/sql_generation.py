from __future__ import annotations

from collections.abc import Sequence

from app.application.prompts.history import render_history_block
from app.domain.conversation import ConversationTurn

SQL_GEN_SYSTEM = """\
You are a senior PostgreSQL analyst. Generate a single, optimized, read-only
SELECT query that answers the user question using ONLY the provided schema.

Hard rules:
- Output ONLY the SQL — no commentary, no markdown, no code fences.
- Exactly ONE statement. No semicolons except the trailing one (optional).
- SELECT only. Never INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/CREATE/GRANT/REVOKE.
- Do not reference tables or columns that are not in the schema.
- Use explicit column lists (no SELECT *).
- Add a LIMIT if the question implies a top-N or could otherwise return many rows.
- Prefer ANSI joins, qualify columns when joining.
- If previous conversation context is provided, the user question may reference
  it (e.g. "and now by country" → reuse the prior aggregation but break it down).
"""

SQL_GEN_USER_TEMPLATE = """\
Database schema:
{schema}
{history_block}
User question (Spanish or English):
\"\"\"{question}\"\"\"

Return only the SQL.
"""

SQL_RETRY_USER_TEMPLATE = """\
Database schema:
{schema}
{history_block}
User question:
\"\"\"{question}\"\"\"

Your previous SQL attempt failed:
--- previous SQL ---
{previous_sql}
--- error from PostgreSQL ---
{error}

Produce a corrected SQL query. Same rules as before. Return only the SQL.
"""


def build_sql_gen_user(
    *,
    schema: str,
    question: str,
    history: Sequence[ConversationTurn] = (),
) -> str:
    return SQL_GEN_USER_TEMPLATE.format(
        schema=schema,
        question=question,
        history_block=render_history_block(history),
    )


def build_sql_retry_user(
    *,
    schema: str,
    question: str,
    previous_sql: str,
    error: str,
    history: Sequence[ConversationTurn] = (),
) -> str:
    return SQL_RETRY_USER_TEMPLATE.format(
        schema=schema,
        question=question,
        previous_sql=previous_sql,
        error=error,
        history_block=render_history_block(history),
    )
