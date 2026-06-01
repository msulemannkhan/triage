"""In-memory conversation repository — for tests and key-less local dev."""

from .conversation_repository import ConversationRepository


class InMemoryConversationRepository(ConversationRepository):
    def __init__(self) -> None:
        self._customer_by_conversation: dict[str, str] = {}

    async def add(self, conversation_id: str, customer_id: str) -> None:
        self._customer_by_conversation[conversation_id] = customer_id

    async def get_customer_id(self, conversation_id: str) -> str | None:
        return self._customer_by_conversation.get(conversation_id)
