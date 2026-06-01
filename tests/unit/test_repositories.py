"""M8a: in-memory conversation + audit repositories."""

from triage.conversations.models.enums import (
    BusinessImpact,
    ConversationStatus,
    NextAction,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import AuditEntry, RoutingDecision
from triage.conversations.repositories.memory_audit_repository import InMemoryAuditRepository
from triage.conversations.repositories.memory_conversation_repository import (
    InMemoryConversationRepository,
)


async def test_conversation_repo_maps_conversation_to_customer():
    repo = InMemoryConversationRepository()
    await repo.add("conv-1", "cust_4821")
    assert await repo.get_customer_id("conv-1") == "cust_4821"
    assert await repo.get_customer_id("unknown") is None


def _entry(conversation_id: str) -> AuditEntry:
    return AuditEntry(
        conversation_id=conversation_id,
        customer_id="cust_4821",
        status=ConversationStatus.resolved,
        decision=RoutingDecision(
            primary_owner=Team.billing_ops,
            next_action=NextAction.route_to_queue,
            effective_urgency=Urgency.high,
            effective_business_impact=BusinessImpact.high,
            rules_fired=["R1"],
        ),
    )


async def test_audit_repo_appends_and_filters_by_conversation():
    repo = InMemoryAuditRepository()
    await repo.append(_entry("conv-1"))
    await repo.append(_entry("conv-1"))
    await repo.append(_entry("conv-2"))

    assert len(await repo.list_for("conv-1")) == 2
    assert len(await repo.list_for("conv-2")) == 1
    assert await repo.list_for("none") == []
