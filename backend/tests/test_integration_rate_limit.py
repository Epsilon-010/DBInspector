"""End-to-end test of the slowapi rate limiter. Uses the real `create_app` so this
also covers: lifespan, CORSMiddleware, SlowAPIMiddleware, GraphQLRouter mount, /health.

Strategy: configure a 2/minute limit, hit /health 3x — third call must return 429.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_tight_limit(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://stub:stub@localhost/stub")
    monkeypatch.setenv("API_RATE_LIMIT", "2/minute")

    # Import inside the fixture so env vars are seen by load_settings()
    from app.api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


def test_health_endpoint_responds_within_limit(app_with_tight_limit: TestClient) -> None:
    r = app_with_tight_limit.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_third_request_returns_429(app_with_tight_limit: TestClient) -> None:
    r1 = app_with_tight_limit.get("/health")
    r2 = app_with_tight_limit.get("/health")
    r3 = app_with_tight_limit.get("/health")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    # slowapi's default 429 body mentions the limit; check the error message surfaces
    body_text = r3.text.lower()
    assert "rate limit" in body_text or "2 per" in body_text


def test_full_app_mounts_graphql_route(app_with_tight_limit: TestClient) -> None:
    """Health probe through the GraphQL endpoint — verifies the schema is mounted."""
    # First request consumes 1/2 of our tight limit; that's fine, we just need the route to exist.
    r = app_with_tight_limit.post("/graphql", json={"query": "{ health }"})
    assert r.status_code == 200
    assert r.json()["data"]["health"] == "ok"
