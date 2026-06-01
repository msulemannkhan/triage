"""Abstract audit repository — the append-only decision log."""

from abc import ABC, abstractmethod

from triage.conversations.models.schemas import AuditEntry


class AuditRepository(ABC):
    @abstractmethod
    async def append(self, entry: AuditEntry) -> None: ...

    @abstractmethod
    async def list_for(self, conversation_id: str) -> list[AuditEntry]: ...
