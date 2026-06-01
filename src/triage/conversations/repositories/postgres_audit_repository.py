"""Postgres implementation of the append-only audit repository (psycopg).

The ``RoutingDecision`` is stored as JSONB so the full rationale (rules fired,
escalations, etc.) is queryable.
"""

from psycopg.types.json import Json

from triage.conversations.models.enums import ConversationStatus
from triage.conversations.models.schemas import AuditEntry, RoutingDecision
from triage.core.database import DictRowPool
from triage.core.logging import get_logger

from .audit_repository import AuditRepository

_log = get_logger("repository")


def _row_to_entry(row: dict) -> AuditEntry:
    decision = RoutingDecision.model_validate(row["decision"]) if row["decision"] else None
    return AuditEntry(
        conversation_id=row["conversation_id"],
        customer_id=row["customer_id"],
        status=ConversationStatus(row["status"]),
        decision=decision,
        clarification=row["clarification"],
    )


class PostgresAuditRepository(AuditRepository):
    def __init__(self, pool: DictRowPool) -> None:
        self._pool = pool

    async def append(self, entry: AuditEntry) -> None:
        decision = Json(entry.decision.model_dump(mode="json")) if entry.decision else None
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO audit_entries "
                "(conversation_id, customer_id, status, decision, clarification) "
                "VALUES (%s, %s, %s, %s, %s)",
                (entry.conversation_id, entry.customer_id, entry.status.value, decision,
                 entry.clarification),
            )
        _log.debug(
            "audit_appended",
            conversation_id=entry.conversation_id,
            status=entry.status.value,
            has_decision=entry.decision is not None,
        )

    async def list_for(self, conversation_id: str) -> list[AuditEntry]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT conversation_id, customer_id, status, decision, clarification "
                "FROM audit_entries WHERE conversation_id = %s ORDER BY id",
                (conversation_id,),
            )
            rows = await cur.fetchall()
        return [_row_to_entry(row) for row in rows]
