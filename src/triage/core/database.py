"""Postgres connection pool + schema DDL (psycopg).

One driver for everything: the same pool backs both the repositories and the
LangGraph ``AsyncPostgresSaver`` checkpointer. Connections are autocommit with a
dict row factory, as the checkpointer requires.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from triage.core.logging import get_logger

# The pool's connections use dict_row at runtime (set via kwargs), but psycopg's
# generics can't infer that from a kwarg — so we name the true type here.
DictRowPool = AsyncConnectionPool[AsyncConnection[DictRow]]

# A fixed, app-specific id for the startup advisory lock (serializes schema setup
# across concurrently-booting api/worker processes).
_SETUP_LOCK_KEY = 0x7141_0001

_log = get_logger("database")


def to_conninfo(database_url: str) -> str:
    """Normalize a SQLAlchemy-style URL to a plain psycopg conninfo string."""
    return database_url.replace("+asyncpg", "").replace("+psycopg", "")


def create_pool(conninfo: str) -> DictRowPool:
    """Create (unopened) an async connection pool configured for psycopg + the
    checkpointer. Call ``await pool.open()`` before use."""
    pool = AsyncConnectionPool(
        conninfo,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )
    return cast(DictRowPool, pool)


_DDL = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_entries (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    customer_id     TEXT NOT NULL,
    status          TEXT NOT NULL,
    decision        JSONB,
    clarification   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_entries_conversation ON audit_entries (conversation_id, id);
"""


async def run_ddl(pool: DictRowPool) -> None:
    """Create our application tables if they don't exist (idempotent)."""
    async with pool.connection() as conn:
        await conn.execute(_DDL)
    _log.info("ddl_applied")


@asynccontextmanager
async def setup_lock(pool: DictRowPool) -> AsyncIterator[None]:
    """Serialize schema setup across concurrently-booting processes with a
    Postgres session-level advisory lock, so N workers don't race on
    ``CREATE TABLE`` / checkpointer migrations at startup."""
    async with pool.connection() as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (_SETUP_LOCK_KEY,))
        _log.debug("setup_lock_acquired")
        try:
            yield
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (_SETUP_LOCK_KEY,))
            _log.debug("setup_lock_released")
