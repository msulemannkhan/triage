"""arq worker definition. Run with:

    uv run arq triage.worker.arq_app.WorkerSettings

On startup it builds a Postgres-backed service (durable checkpointer + repos)
and a Redis-backed conversation lock, shared by every job via ``ctx``.
"""

from arq.connections import RedisSettings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from triage.conversations.orchestration.graph import build_graph
from triage.conversations.repositories.postgres_audit_repository import PostgresAuditRepository
from triage.conversations.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)
from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.conversation_service import ConversationService
from triage.conversations.services.enrichment import make_enricher
from triage.core.config import get_settings
from triage.core.database import create_pool, run_ddl, setup_lock, to_conninfo
from triage.core.logging import configure_logging
from triage.core.redis import create_redis
from triage.providers.factory import make_llm_provider
from triage.worker.concurrency.lock import ConversationLock
from triage.worker.handlers.turn import run_turn_job


async def _startup(ctx: dict) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    pg_pool = create_pool(to_conninfo(settings.database_url))
    await pg_pool.open()
    saver = AsyncPostgresSaver(pg_pool)
    async with setup_lock(pg_pool):  # serialize schema setup across processes
        await run_ddl(pg_pool)
        await saver.setup()
    graph = build_graph(
        make_llm_provider(settings),
        make_enricher(SeededCustomerRepository()),
        clarification_cap=settings.clarification_cap,
        clarification_cap_sensitive=settings.clarification_cap_sensitive,
        checkpointer=saver,
    )
    ctx["pg_pool"] = pg_pool
    ctx["redis_client"] = create_redis(settings.redis_url)
    ctx["service"] = ConversationService(
        graph,
        PostgresConversationRepository(pg_pool),
        PostgresAuditRepository(pg_pool),
    )
    ctx["lock"] = ConversationLock(ctx["redis_client"], settings.lock_lease_seconds)


async def _shutdown(ctx: dict) -> None:
    await ctx["pg_pool"].close()
    await ctx["redis_client"].aclose()


class WorkerSettings:
    functions = [run_turn_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = _startup
    on_shutdown = _shutdown
    max_tries = get_settings().worker_max_tries
