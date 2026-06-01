"""M8a: the service writes an auditable record for every turn."""

from triage.conversations.models.enums import (
    BusinessImpact,
    ConversationStatus,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.graph import build_graph
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.conversation_service import ConversationService
from triage.conversations.services.enrichment import make_enricher
from triage.providers.llm.fake import FakeLLMProvider

BILLING = Understanding(
    issues=[Issue(category=IssueCategory.billing_payments)],
    sentiment=Sentiment.frustrated,
    urgency=Urgency.high,
    business_impact=BusinessImpact.high,
)
VAGUE = Understanding(
    issues=[Issue(category=IssueCategory.other)],
    sentiment=Sentiment.neutral,
    urgency=Urgency.normal,
    business_impact=BusinessImpact.none,
)


def _service(fake: FakeLLMProvider) -> ConversationService:
    graph = build_graph(fake, make_enricher(SeededCustomerRepository()))
    return ConversationService.in_memory(graph)


async def test_resolved_turn_is_audited_with_rationale():
    service = _service(FakeLLMProvider(understanding=BILLING))
    cid = await service.create("cust_4821")
    await service.submit(cid, "billing reports are down")

    log = await service.audit_log(cid)
    assert len(log) == 1
    assert log[0].status is ConversationStatus.resolved
    assert log[0].decision is not None
    assert "R2" in log[0].decision.rules_fired  # enterprise + high urgency


async def test_each_turn_appends_an_audit_entry():
    service = _service(
        FakeLLMProvider(understandings=[VAGUE, BILLING], clarification="Which area?")
    )
    cid = await service.create("cust_2290")

    await service.submit(cid, "something broke")   # clarification turn
    await service.submit(cid, "billing is down")   # resolving turn

    log = await service.audit_log(cid)
    assert len(log) == 2
    assert log[0].status is ConversationStatus.awaiting_customer
    assert log[0].decision is None
    assert log[1].status is ConversationStatus.resolved
    assert log[1].decision is not None
