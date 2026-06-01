"""M4: full pipeline through the LangGraph graph, on deterministic fakes."""

from triage.conversations.models.enums import (
    BusinessImpact,
    ConversationStatus,
    CustomerTier,
    EscalationLevel,
    IssueCategory,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import EnrichmentResult, Issue, Understanding
from triage.conversations.orchestration.graph import build_graph, run_turn, to_packet
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.enrichment import make_enricher
from triage.providers.llm.fake import FakeLLMProvider


def _enterprise_enrich(_customer_id: str) -> EnrichmentResult:
    return EnrichmentResult(tier=CustomerTier.enterprise, prior_interactions=2)


def _unknown_enrich(_customer_id: str) -> EnrichmentResult:
    return EnrichmentResult(tier=CustomerTier.free, known_customer=False)


async def test_full_pipeline_routes_escalates_and_generates():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.billing_payments)],
        sentiment=Sentiment.frustrated,
        urgency=Urgency.high,
        business_impact=BusinessImpact.high,
    )
    graph = build_graph(FakeLLMProvider(understanding=understanding), _enterprise_enrich)

    state = await run_turn(graph, conversation_id="c1", customer_id="cust1", message="billing down")

    assert state.status is ConversationStatus.resolved
    packet = to_packet(state)
    assert packet is not None
    assert packet.routing.primary_owner is Team.billing_ops
    assert EscalationLevel.on_call_engineering in packet.routing.escalations  # R1 (high impact)
    assert packet.customer_reply
    assert "billing_ops" in packet.internal_summary


async def test_underspecified_message_pauses_for_clarification():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.other)],
        sentiment=Sentiment.neutral,
        urgency=Urgency.normal,
        business_impact=BusinessImpact.none,
    )
    graph = build_graph(
        FakeLLMProvider(understanding=understanding, clarification="Which area is affected?"),
        _unknown_enrich,
    )

    state = await run_turn(graph, conversation_id="c2", customer_id="cust2", message="it broke")

    assert state.status is ConversationStatus.awaiting_customer
    assert state.clarification == "Which area is affected?"
    assert state.clarification_count == 1
    assert state.decision is None
    assert to_packet(state) is None


async def test_tie_break_lets_the_llm_pick_the_primary_owner():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.mobile_app)],  # default team: mobile_engineering
        sentiment=Sentiment.neutral,
        urgency=Urgency.high,
        business_impact=BusinessImpact.medium,
    )

    def _enrich_with_conflicting_candidate(_customer_id: str) -> EnrichmentResult:
        return EnrichmentResult(tier=CustomerTier.pro, candidate_team=Team.platform_sre)

    graph = build_graph(
        FakeLLMProvider(understanding=understanding, tie_break_choice=Team.platform_sre),
        _enrich_with_conflicting_candidate,
    )

    state = await run_turn(graph, conversation_id="c3", customer_id="cust3", message="app issue")

    assert state.decision is not None
    assert state.decision.primary_owner is Team.platform_sre  # LLM resolved the tie
    assert "T1" in state.decision.rules_fired


async def test_tie_break_fires_through_the_real_enricher():
    # Regression guard: the tie-break must be reachable in *production* wiring, not
    # only when a test hand-builds candidate_team. cust_2290 is web+api, so the
    # enricher derives candidate_team=api_integrations_team; an authentication
    # message routes to identity_access by default -> a genuine, non-critical tie.
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.authentication)],  # default: identity_access
        sentiment=Sentiment.neutral,
        urgency=Urgency.high,
        business_impact=BusinessImpact.medium,
    )
    graph = build_graph(
        FakeLLMProvider(understanding=understanding, tie_break_choice=Team.api_integrations_team),
        make_enricher(SeededCustomerRepository()),
    )

    state = await run_turn(
        graph, conversation_id="c4", customer_id="cust_2290", message="can't log in"
    )

    assert state.decision is not None
    assert "T1" in state.decision.rules_fired  # the tie-break actually ran
    assert state.decision.primary_owner is Team.api_integrations_team
