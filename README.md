# DBInspector

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)

Ask a Postgres database a question in plain Spanish. Get back the SQL it generated,
the data, a chart, and a short executive summary, all streamed live as the
pipeline runs.

## What it does

You type something like *"top 5 best-selling products this year"*. Behind the scenes:

1. An AI guardrail rejects the question if it tries to mutate data, leak credentials, or inject instructions.
2. Claude generates a single read-only `SELECT` using the live database schema as context.
3. `sqlglot` parses the SQL at the AST level and refuses anything that isn't a single `SELECT` (no DDL, no DML, no multi-statement).
4. Postgres runs it under a read-only transaction, a 15s `statement_timeout`, and a row cap, using a role with no write privileges.
5. Pandas cleans the rows.
6. Claude writes a short Spanish summary and picks a chart spec (`bar`, `line`, `pie`, ...).

Every stage publishes events to a `asyncio.Queue`, exposed as a GraphQL Subscription so
the frontend can show progress live.

Multi-turn: each follow-up question carries the prior turn's question, SQL, and
summary as context. The conversation id lives in the URL (`?c=<id>`) so a reload
restores the thread.

## Stack

**Backend** — Python 3.11+
- FastAPI + Strawberry GraphQL (queries, mutations, WebSocket subscriptions)
- LangGraph orchestrator with conditional edges for retry/reject
- LangChain + Anthropic Claude Sonnet 4.6, with prompt caching on system messages
- SQLAlchemy async + asyncpg + PostgreSQL 16
- sqlglot for AST validation, pandas for post-processing
- slowapi for per-IP rate limiting
- pytest + pytest-asyncio (112 tests, ~2s, no network)

**Frontend** — React 19 + TypeScript
- Vite, Tailwind, axios
- graphql-ws for subscriptions
- Recharts, lazy-loaded so the initial bundle stays at 84 kB gzipped

**Infra**
- Docker + docker-compose: Postgres + backend + frontend behind nginx
- Chinook sample database, seeded on first boot

## Architecture

Hexagonal. Strict dependency direction, inward only:

```
domain/        entities, events, errors (no I/O, no frameworks)
application/   use cases (orchestrator + 5 pipeline nodes) and ports (Protocols)
adapters/      Claude, Postgres, sqlglot, asyncio bus, demo, in-memory stores
api/           driving adapter: FastAPI + Strawberry GraphQL
observability/ JSON logger + request_id contextvar for correlation
```

Tests inject fakes through the same `Protocol`s the production adapters implement,
which is why the suite runs in 2 seconds without touching the network.

## Running it

You need Docker. That's it.

```bash
git clone <this-repo>
cd DBInspector
cp backend/.env.example backend/.env

# Real mode: edit backend/.env, set DEMO_MODE=false and paste your ANTHROPIC_API_KEY.
# Demo mode: leave DEMO_MODE=true (default) — no key, no DB, canned offline responses.

docker compose up -d --build
# UI:        http://localhost:8080
# GraphQL:   http://localhost:8000/graphql (GraphiQL)
# Postgres:  localhost:5433 (host port)
```

The Chinook schema and data are loaded automatically on first boot.

## Tests

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate  # or .venv/bin/activate on Linux/Mac
pip install -e ".[api,dev]"
pytest -q
```

## Project layout

```
DBInspector/
├── backend/
│   ├── app/
│   │   ├── domain/        # entities + events + errors
│   │   ├── application/   # pipeline (orchestrator + nodes), ports, prompts
│   │   ├── adapters/      # llm/, db/, sql/, event_bus/, conversation/, demo/
│   │   ├── api/           # graphql/, session_manager, app
│   │   ├── observability/ # structured logging + request_id contextvar
│   │   ├── composition.py # composition root: wires adapters into the orchestrator
│   │   └── config.py
│   ├── db/init/           # Chinook seed + read-only role grant
│   └── tests/
└── frontend/
    └── src/
        ├── domain/        # TypeScript mirror of the backend models
        ├── api/           # graphql clients (queries, mutations, subscriptions)
        ├── features/
        │   ├── chat/      # multi-turn conversation hook + thread view
        │   └── query/     # progress timeline + input
        ├── components/    # Card, Button, DataTable, ChartRenderer, CollapsiblePanel
        └── lib/           # env + conversation-id URL sync
```

## Security

Defense in depth. Each layer is independent of the others:

| Layer | What it stops |
|-------|---------------|
| AI guardrail | Malicious *questions*: prompt injection, "delete the users table", "ignore prior instructions" |
| sqlglot validator | Malicious *SQL*: DDL/DML, multi-statement, anything that isn't a `SELECT` |
| Read-only Postgres role | Mutations that would slip past the above |
| `statement_timeout` + row cap | Runaway queries and oversized result sets |

The guardrail and the validator catch different things on purpose. A benign question
can still lead a hallucinating LLM to emit DDL; the validator catches that even
though the guardrail let the question through.

## Notes

- The frontend pins `axios@1.15.1`. Versions `1.14.1` and `0.30.4` were compromised in the *Sapphire Sleet* supply-chain attack in March 2026.
- Conversation history and pipeline sessions are kept in-memory with LRU eviction. Swapping for Redis or Postgres is a port-level change; nothing above the adapter touches them.
- The system prompt for each LLM call is sent with `cache_control: ephemeral`. On Anthropic's prompt cache, repeat calls within 5 minutes cost ~10% of fresh input tokens.
