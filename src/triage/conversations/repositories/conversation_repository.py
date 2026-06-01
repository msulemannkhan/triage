"""Abstract conversation repository — maps a conversation to its customer.

(The orchestration *state* lives in the checkpointer; this just records which
customer a conversation belongs to so follow-up turns carry the right context.)
Async so the Postgres implementation drops in without changing the service.
"""

from abc import ABC, abstractmethod


class ConversationRepository(ABC):
    @abstractmethod
    async def add(self, conversation_id: str, customer_id: str) -> None: ...

    @abstractmethod
    async def get_customer_id(self, conversation_id: str) -> str | None: ...
