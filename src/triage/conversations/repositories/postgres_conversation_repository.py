"""Postgres implementation of the conversation repository (psycopg)."""

from triage.core.database import DictRowPool
from triage.core.logging import get_logger

from .conversation_repository import ConversationRepository

_log = get_logger("repository")


class PostgresConversationRepository(ConversationRepository):
    def __init__(self, pool: DictRowPool) -> None:
        self._pool = pool

    async def add(self, conversation_id: str, customer_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO conversations (conversation_id, customer_id) "
                "VALUES (%s, %s) ON CONFLICT (conversation_id) DO NOTHING",
                (conversation_id, customer_id),
            )
        _log.debug("conversation_added", conversation_id=conversation_id, customer_id=customer_id)

    async def get_customer_id(self, conversation_id: str) -> str | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT customer_id FROM conversations WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = await cur.fetchone()
        found = row is not None
        _log.debug("conversation_lookup", conversation_id=conversation_id, found=found)
        return row["customer_id"] if row else None
