# DBInspector

Read-only Business Intelligence platform: a user asks a natural-language question
("top 5 best-selling products this year"), and gets back the generated SQL, the
result table, a chart, and an executive summary in Spanish — all streamed live
to the client while the AI agent pipeline runs.

## Repo layout (monorepo)

```
DBInspector/
├── backend/         Python 3.11+ — hexagonal: domain · application · adapters · api
│   └── app/
│       ├── domain/        pure entities + events + errors (no I/O, no frameworks)
│       ├── application/   use cases (pipeline orchestrator + nodes) and ports
│       ├── adapters/      infra implementations of the ports
│       │                  (Claude LLM, Postgres, sqlglot validator, asyncio bus)
│       ├── api/           driving adapter — FastAPI + Strawberry GraphQL
│       ├── composition.py composition root (wires adapters into the orchestrator)
│       └── main.py        CLI demo entry point
└── frontend/        (TBD — React or Streamlit consuming GraphQL Subscriptions)
```

The hexagonal direction is strict: `adapters/` and `api/` depend on
`application/`; `application/` depends on `domain/`; `domain/` depends on
nothing. Inverting the arrow is a smell.

## Backend pipeline (the "graph")

5 async nodes, executed by a custom orchestrator. Each node emits events to an
`asyncio.Queue` so GraphQL Subscriptions can stream progress to the client.

```
question
    │
    ▼
┌─────────────┐  unsafe?  ┌──────────────┐
│  Guardrail  │──────────▶│  REJECTED    │
└──────┬──────┘           └──────────────┘
       │ safe
       ▼
┌─────────────┐
│ SQL Generator│ ◀──── retry with error context (max 2)
└──────┬───────┘
       ▼
┌─────────────┐  fails?
│ SQL Executor│──────────▶ back to generator
└──────┬──────┘
       │ ok
       ▼
┌─────────────┐
│ Data Proc.  │  (Pandas: clean, structure)
└──────┬──────┘
       ▼
┌─────────────┐
│  Analyzer   │  (LLM: summary + chart spec JSON)
└──────┬──────┘
       ▼
   final result
```

The retry loop lives in the **orchestrator** (control flow), not the executor
node (which stays a pure transformation). This keeps SOLID clean and makes the
graph trivial to port to LangGraph in v2.

## Architectural principles (non-negotiable)

- **Async everywhere.** `asyncio` + `sqlalchemy[asyncio]` + `anthropic.AsyncAnthropic`.
- **SOLID.**
  - Each node has one responsibility.
  - Interfaces are `typing.Protocol` (`LLMClient`, `Database`, `Node`).
  - Dependency injection via constructor — orchestrator depends on abstractions.
- **Defense in depth (security):**
  1. AI guardrail rejects injection attempts and destructive keywords.
  2. SQL parser validates the generated query is a single read-only `SELECT` (AST, not regex).
  3. PostgreSQL connection uses a real `read-only` role.
  4. Statement timeout on every query.
- **LangChain + LangGraph in MVP.** The default `LLMClient` adapter is
  `LangChainLLMClient` (wraps `ChatAnthropic`). The orchestrator is a
  `langgraph.StateGraph` (`application/pipeline/orchestrator.py`). The direct
  Anthropic SDK adapter (`ClaudeLLMClient`) is kept as an alternate, easy to
  swap from `composition.py`.

## Stack

| Layer       | Choice                                                        |
| ----------- | ------------------------------------------------------------- |
| API         | FastAPI + Strawberry GraphQL (Mutations + Subscriptions)      |
| Rate limit  | slowapi (per-IP, configurable via `API_RATE_LIMIT`)           |
| LLM         | Anthropic Claude (`claude-sonnet-4-6` default, override by env) via `langchain-anthropic` |
| Orchestrator| LangGraph `StateGraph` with conditional edges for retry/reject |
| DB driver   | SQLAlchemy 2.x async + `asyncpg`                              |
| Data        | Pandas                                                        |
| DB          | PostgreSQL (Neon.tech) with read-only role                    |
| Container   | Docker + docker-compose                                       |
| Deploy      | Railway                                                       |

## Roadmap (v2 — NOT in MVP, README only)

- **PySpark** when data volume justifies it.
- **Prophet** for time-series forecasting.
- **Hybrid model routing**: Sonnet for hard tasks, Haiku for fast validations.
- **Auth + per-user query history** in a separate metadata DB.

## Running the backend

```bash
cd backend
cp .env.example .env   # fill ANTHROPIC_API_KEY and DATABASE_URL
pip install -e ".[api,dev]"

# Option A — CLI demo (one-shot, prints events + final report)
python -m app.main "¿Cuáles son los 5 productos más vendidos este año?"

# Option B — GraphQL server
uvicorn app.api.app:app --reload
# GraphiQL UI: http://localhost:8000/graphql
```

GraphQL endpoints (all defined in `app/api/graphql/schema.py`):

| Op           | Field                       | Purpose                                    |
| ------------ | --------------------------- | ------------------------------------------ |
| Mutation     | `runQuery(question)`        | Start a pipeline run, returns a `requestId`. |
| Subscription | `progress(requestId)`       | Stream `progress` / `rejected` / `failed` / `result` events. |
| Query        | `report(requestId)`         | Fetch the final report after the run finished (in case the client lost the stream). |
| Query        | `health`                    | Liveness probe.                            |

Sessions live in-memory in `api/session_manager.py`. v2 swap for Redis pub/sub
when scaling beyond a single process.

## Tests

```bash
cd backend
pytest               # 73 unit tests, ~1s, no DB/LLM/network
pytest tests/test_orchestrator.py -v   # just the 4 graph flow scenarios
```

Layout under `backend/tests/`:

| File                            | Covers                                                  |
| ------------------------------- | ------------------------------------------------------- |
| `conftest.py`                   | `FakeLLM`, `FakeIntrospector`, `FakeDatabase`, `FakeValidator`. |
| `test_domain.py`                | Pure pydantic models (`Question`, `SchemaSnapshot`, …). |
| `test_sqlglot_validator.py`     | Accepts SELECT/CTE/UNION; rejects DDL/DML/multi-stmt.   |
| `test_event_bus.py`             | publish / stream / close / sentinel; close idempotency. |
| `test_claude_client_helpers.py` | `_parse_json_object` with fences, prose, errors.        |
| `test_session_manager.py`       | register/get/discard + LRU eviction.                    |
| `test_nodes.py`                 | Each pipeline node in isolation with fakes.             |
| `test_orchestrator.py`          | The 4 graph flow scenarios end-to-end.                  |

Tests run on the project venv (`uv pip install pytest pytest-asyncio` once).
`asyncio_mode = "auto"` in `pyproject.toml` auto-detects async tests.

## Working agreements

- **Communicate in Spanish** with the user. Code, identifiers, and code
  comments stay in English (industry standard).
- Default to writing **no code comments**. Add one only when the *why* is
  non-obvious.
- Resist over-engineering. Every choice must be defensible in a Backend Junior
  interview. If it's "v2", it doesn't ship in MVP code.
