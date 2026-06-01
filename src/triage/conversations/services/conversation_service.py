"""Application service that drives the orchestration graph.

It owns conversation identity (minting ids, mapping conversation -> customer via
the conversation repository) and writes an audit entry for every turn. It feeds
context to the graph from validated request data — never from raw message text.
Repositories are injected, so the same service runs on in-memory stores (tests)
or Postgres (production) without change.
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog

from triage.conversations.models.enums import ConversationStatus
from triage.conversations.models.schemas import AuditEntry
from triage.conversations.models.state import GraphState
from triage.conversations.orchestration.graph import run_turn
from triage.conversations.repositories.audit_repository import AuditRepository
from triage.conversations.repositories.conversation_repository import ConversationRepository
from triage.conversations.repositories.memory_audit_repository import InMemoryAuditRepository
from triage.conversations.repositories.memory_conversation_repository import (
    InMemoryConversationRepository,
)
from triage.core.errors import NotFoundError
from triage.core.logging import get_logger

_log = get_logger("conversation")


class ConversationService:
    def __init__(
        self,
        graph,
        conversations: ConversationRepository,
        audit: AuditRepository,
    ) -> None:
        self._graph = graph
        self._conversations = conversations
        self._audit = audit

    @classmethod
    def in_memory(cls, graph) -> "ConversationService":
        """Wire the service with in-memory repositories (tests / key-less dev)."""
        return cls(graph, InMemoryConversationRepository(), InMemoryAuditRepository())

    async def create(self, customer_id: str) -> str:
        conversation_id = uuid.uuid4().hex
        await self._conversations.add(conversation_id, customer_id)
        return conversation_id

    async def _require_customer(self, conversation_id: str) -> str:
        customer_id = await self._conversations.get_customer_id(conversation_id)
        if customer_id is None:
            raise NotFoundError(f"Unknown conversation: {conversation_id}")
        return customer_id

    async def submit(
        self,
        conversation_id: str,
        text: str,
        on_node: Callable[[str], Awaitable[None]] | None = None,
    ) -> GraphState:
        with structlog.contextvars.bound_contextvars(conversation_id=conversation_id):
            customer_id = await self._require_customer(conversation_id)
            state = await run_turn(
                self._graph,
                conversation_id=conversation_id,
                customer_id=customer_id,
                message=text,
                on_node=on_node,
            )
            await self._audit.append(
                AuditEntry(
                    conversation_id=conversation_id,
                    customer_id=customer_id,
                    status=state.status,
                    decision=state.decision,
                    clarification=state.clarification,
                )
            )
            _log.info(
                "turn_processed",
                status=state.status.value,
                primary_owner=state.decision.primary_owner.value if state.decision else None,
                rules_fired=state.decision.rules_fired if state.decision else None,
            )
            return state

    async def get(self, conversation_id: str) -> GraphState:
        customer_id = await self._require_customer(conversation_id)
        snapshot = await self._graph.aget_state({"configurable": {"thread_id": conversation_id}})
        if snapshot.values:
            return GraphState.model_validate(snapshot.values)
        return GraphState(
            conversation_id=conversation_id,
            customer_id=customer_id,
            message="",
            status=ConversationStatus.active,
        )

    async def audit_log(self, conversation_id: str) -> list[AuditEntry]:
        await self._require_customer(conversation_id)
        return await self._audit.list_for(conversation_id)
