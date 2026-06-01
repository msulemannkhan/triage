"""M5: the graph runs on the real seeded enrichment (no stub)."""

from triage.conversations.models.enums import (
    BusinessImpact,
    CustomerTier,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.graph import build_graph, run_turn
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.enrichment import make_enricher
from triage.providers.llm.fake import FakeLLMProvider


async def test_graph_pulls_enterprise_context_from_the_fixture():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.billing_payments)],
        sentiment=Sentiment.frustrated,
        urgency=Urgency.high,
        business_impact=BusinessImpact.high,
    )
    enrich = make_enricher(SeededCustomerRepository())
    graph = build_graph(FakeLLMProvider(understanding=understanding), enrich)

    state = await run_turn(
        graph, conversation_id="c1", customer_id="cust_4821", message="billing reports are down"
    )

    assert state.enrichment is not None
    assert state.enrichment.tier is CustomerTier.enterprise  # pulled from the fixture
    assert state.decision is not None
    # enterprise + high urgency -> R2 (notify CSM) must have fired
    assert "R2" in state.decision.rules_fired


async def test_graph_handles_unknown_customer_with_defaults():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.billing_payments)],
        sentiment=Sentiment.neutral,
        urgency=Urgency.high,
        business_impact=BusinessImpact.high,
    )
    enrich = make_enricher(SeededCustomerRepository())
    graph = build_graph(FakeLLMProvider(understanding=understanding), enrich)

    state = await run_turn(
        graph, conversation_id="c2", customer_id="ghost", message="billing reports are down"
    )

    assert state.enrichment is not None
    assert state.enrichment.known_customer is False
    assert state.enrichment.tier is CustomerTier.free
    # unknown free customer -> R2 (enterprise) must NOT fire
    assert state.decision is not None
    assert "R2" not in state.decision.rules_fired
