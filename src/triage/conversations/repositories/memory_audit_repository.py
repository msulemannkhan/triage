"""In-memory audit repository — for tests and key-less local dev."""

from triage.conversations.models.schemas import AuditEntry

from .audit_repository import AuditRepository


class InMemoryAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    async def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    async def list_for(self, conversation_id: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.conversation_id == conversation_id]
