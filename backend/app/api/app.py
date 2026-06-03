from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL

from app.api.graphql.schema import GraphQLContext, schema
from app.api.session_manager import SessionManager
from app.composition import Container
from app.config import load_settings
from app.observability import setup_logging


def create_app() -> FastAPI:
    settings = load_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        container = Container.build(settings)
        sessions = SessionManager()
        app.state.container = container
        app.state.sessions = sessions
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(title="DBInspector", version="0.1.0", lifespan=lifespan)

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.api_rate_limit],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def get_context() -> GraphQLContext:
        return GraphQLContext(container=app.state.container, sessions=app.state.sessions)

    graphql_router = GraphQLRouter[GraphQLContext, None](
        schema,
        context_getter=get_context,
        subscription_protocols=[
            GRAPHQL_TRANSPORT_WS_PROTOCOL,
            GRAPHQL_WS_PROTOCOL,
        ],
    )
    app.include_router(graphql_router, prefix="/graphql")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
