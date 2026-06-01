"""FastAPI application factory.

`create_app()` wires the error envelope, routers, and a ConversationService. The
service defaults to in-memory state on the heuristic (key-less) LLM provider; the
lifespan upgrades it on startup based on settings:

- `TRIAGE_PERSISTENCE=postgres` -> durable Postgres-backed service.
- `TRIAGE_EXECUTION=queue`     -> a QueueSubmitter that enqueues turns to the arq
                                  worker (the worker runs the graph); else the
                                  graph runs in-request.

Tests inject a service (and stay in-memory/inline). Run with:
``uv run uvicorn triage.main:app --reload``.
"""

from contextlib import asynccontextmanager

from arq import create_pool as arq_create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from triage.conversations.api.v1.endpoints import conversations, health, jobs
from triage.conversations.orchestration.graph import build_graph
from triage.conversations.repositories.postgres_audit_repository import PostgresAuditRepository
from triage.conversations.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.conversation_service import ConversationService
from triage.conversations.services.enrichment import make_enricher
from triage.core.config import get_settings
from triage.core.database import create_pool, run_ddl, setup_lock, to_conninfo
from triage.core.logging import configure_logging, get_logger
from triage.core.middleware.error_handlers import register_error_handlers
from triage.core.pubsub import ProgressBus
from triage.core.redis import create_redis
from triage.providers.factory import make_llm_provider, make_transcriber
from triage.worker.concurrency.idempotency import IdempotencyStore
from triage.worker.submitter import QueueSubmitter

configure_logging(get_settings().log_level)

_log = get_logger("app")


def _build_graph(checkpointer=None):
    settings = get_settings()
    return build_graph(
        make_llm_provider(settings),
        make_enricher(SeededCustomerRepository()),
        clarification_cap=settings.clarification_cap,
        clarification_cap_sensitive=settings.clarification_cap_sensitive,
        checkpointer=checkpointer,
    )


def _default_service() -> ConversationService:
    return ConversationService.in_memory(_build_graph())


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    pg_pool = arq_pool = redis_client = None

    if settings.api_key == "dev-key" and (
        settings.persistence == "postgres" or settings.execution == "queue"
    ):
        _log.warning(
            "default_api_key_in_use",
            detail="TRIAGE_API_KEY is the built-in default while running in a durable/queue mode; "
            "set a strong key before exposing this service",
        )

    if settings.persistence == "postgres":
        pg_pool = create_pool(to_conninfo(settings.database_url))
        await pg_pool.open()
        saver = AsyncPostgresSaver(pg_pool)
        async with setup_lock(pg_pool):  # serialize schema setup across processes
            await run_ddl(pg_pool)
            await saver.setup()
        app.state.service = ConversationService(
            _build_graph(checkpointer=saver),
            PostgresConversationRepository(pg_pool),
            PostgresAuditRepository(pg_pool),
        )

    if settings.execution == "queue":
        arq_pool = await arq_create_pool(RedisSettings.from_dsn(settings.redis_url))
        redis_client = create_redis(settings.redis_url)
        app.state.submitter = QueueSubmitter(
            arq_pool, IdempotencyStore(redis_client, settings.idempotency_ttl_seconds)
        )
        app.state.progress_bus = ProgressBus(redis_client)
        _log.info("queue_mode_enabled", persistence=settings.persistence)

    app.state.pg_pool, app.state.arq_pool, app.state.redis_client = pg_pool, arq_pool, redis_client
    try:
        yield
    finally:
        if pg_pool is not None:
            await pg_pool.close()
        if arq_pool is not None:
            await arq_pool.close()
        if redis_client is not None:
            await redis_client.aclose()


def create_app(service: ConversationService | None = None) -> FastAPI:
    app = FastAPI(title="Triage Orchestrator", version="0.1.0", lifespan=_lifespan)
    app.state.service = service or _default_service()
    app.state.submitter = None  # set by the lifespan in queue mode
    app.state.progress_bus = None  # set by the lifespan in queue mode
    app.state.transcriber = make_transcriber(get_settings())
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(conversations.router, prefix="/v1")
    app.include_router(jobs.router, prefix="/v1")
    return app


app = create_app()
