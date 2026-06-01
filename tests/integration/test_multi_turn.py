"""M6: multi-turn — clarify then resume, and the max-turns guard, over a
checkpointed thread (in-memory)."""

from triage.conversations.models.enums import (
    BusinessImpact,
    ConversationStatus,
    IssueCategory,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.graph import build_graph, run_turn
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.enrichment import make_enricher
from triage.providers.llm.fake import FakeLLMProvider

VAGUE = Understanding(
    issues=[Issue(category=IssueCategory.other)],
    sentiment=Sentiment.frustrated,
    urgency=Urgency.normal,
    business_impact=BusinessImpact.none,
)
CLEAR = Understanding(
    issues=[Issue(category=IssueCategory.api_integrations)],
    sentiment=Sentiment.frustrated,
    urgency=Urgency.high,
    business_impact=BusinessImpact.high,
)


def _enricher():
    return make_enricher(SeededCustomerRepository())


async def test_clarify_then_resume_resolves_with_accumulated_context():
    # turn 1 is vague -> a clarifying question; turn 2 is clear -> resolves.
    fake = FakeLLMProvider(understandings=[VAGUE, CLEAR], clarification="Which area is affected?")
    graph = build_graph(fake, _enricher())

    turn1 = await run_turn(
        graph, conversation_id="conv-1", customer_id="cust_2290", message="something is broken"
    )
    assert turn1.status is ConversationStatus.awaiting_customer
    assert turn1.clarification == "Which area is affected?"
    assert turn1.clarification_count == 1
    assert turn1.decision is None

    turn2 = await run_turn(
        graph, conversation_id="conv-1", customer_id="cust_2290", message="the API returns 500s"
    )
    assert turn2.status is ConversationStatus.resolved
    assert turn2.decision is not None
    assert turn2.understanding is not None
    # merged understanding routed on the clarified issue; the 'other' placeholder is gone
    categories = {i.category for i in turn2.understanding.issues}
    assert categories == {IssueCategory.api_integrations}
    assert turn2.decision.primary_owner is Team.api_integrations_team


async def test_resolving_a_turn_resets_the_clarification_count():
    # The max-turns guard is per clarification *episode*: once a turn resolves the
    # counter returns to zero, so a later under-specified message isn't penalised
    # by questions asked in a previous, already-closed episode.
    fake = FakeLLMProvider(understandings=[VAGUE, CLEAR], clarification="Which area is affected?")
    graph = build_graph(fake, _enricher())

    t1 = await run_turn(
        graph, conversation_id="conv-3", customer_id="cust_2290", message="something is broken"
    )
    assert t1.clarification_count == 1  # asked once

    t2 = await run_turn(
        graph, conversation_id="conv-3", customer_id="cust_2290", message="the API returns 500s"
    )
    assert t2.status is ConversationStatus.resolved
    assert t2.clarification_count == 0  # reset on resolve


async def test_clarification_budget_exhausted_forces_a_human():
    # stays vague every turn; with cap=2, the third turn force-routes to a human.
    fake = FakeLLMProvider(understanding=VAGUE)
    graph = build_graph(fake, _enricher(), clarification_cap=2)

    t1 = await run_turn(graph, conversation_id="conv-2", customer_id="cust_2290", message="m1")
    t2 = await run_turn(graph, conversation_id="conv-2", customer_id="cust_2290", message="m2")
    assert t1.clarification_count == 1
    assert t2.clarification_count == 2
    assert t2.status is ConversationStatus.awaiting_customer

    t3 = await run_turn(graph, conversation_id="conv-2", customer_id="cust_2290", message="m3")
    assert t3.status is ConversationStatus.resolved
    assert t3.decision is not None
    assert t3.decision.rules_fired == ["GATE_EXHAUSTED"]
    assert t3.decision.primary_owner is Team.tier1_support
    assert t3.decision.human_review_required is True
