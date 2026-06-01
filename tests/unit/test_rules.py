"""M2: the routing & escalation policy end-to-end (scenario tests)."""

from triage.conversations.decision.rules import route
from triage.conversations.models.enums import (
    BusinessImpact,
    CustomerTier,
    EscalationLevel,
    IssueCategory,
    NextAction,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import EnrichmentResult, Issue, Understanding


def test_multi_issue_enterprise_high_impact_escalates_and_goes_to_human():
    understanding = Understanding(
        issues=[
            Issue(category=IssueCategory.mobile_app),
            Issue(category=IssueCategory.reporting_analytics),
            Issue(category=IssueCategory.billing_payments),
        ],
        sentiment=Sentiment.frustrated,
        urgency=Urgency.high,
        business_impact=BusinessImpact.high,
        escalation_signal=True,
    )
    enrichment = EnrichmentResult(tier=CustomerTier.enterprise, prior_interactions=2)

    decision = route(understanding, enrichment)

    # M1 bumped high -> critical; M3 then forces a human.
    assert decision.effective_urgency is Urgency.critical
    assert decision.human_review_required is True
    # R1 (impact) -> on-call + incident; R2 (enterprise+high) -> notify CSM.
    assert EscalationLevel.on_call_engineering in decision.escalations
    assert EscalationLevel.account_manager in decision.escalations
    assert decision.next_action is NextAction.create_incident
    # Primary owner is the highest-priority issue (billing here); others are tagged.
    assert decision.primary_owner is Team.billing_ops
    assert Team.mobile_engineering in decision.secondary_tags
    assert {"M1", "R1", "R2", "M4", "M3"}.issubset(set(decision.rules_fired))


def test_calm_howto_is_auto_resolved():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.how_to_guidance)],
        sentiment=Sentiment.neutral,
        urgency=Urgency.low,
        business_impact=BusinessImpact.none,
    )
    decision = route(understanding, EnrichmentResult(tier=CustomerTier.free))

    assert decision.next_action is NextAction.auto_resolve_with_kb
    assert decision.escalations == []
    assert decision.human_review_required is False
    assert decision.primary_owner is Team.tier1_support
    assert decision.rules_fired == ["A1"]


def test_data_privacy_always_routes_to_trust_with_tier2():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.data_export_privacy)],
        sentiment=Sentiment.neutral,
        urgency=Urgency.normal,
        business_impact=BusinessImpact.low,
    )
    decision = route(understanding, EnrichmentResult(tier=CustomerTier.business))

    assert decision.primary_owner is Team.trust_privacy
    assert EscalationLevel.tier2 in decision.escalations
    assert "R4" in decision.rules_fired


def test_explicit_escalation_signal_forces_human_without_auto_resolve():
    understanding = Understanding(
        issues=[Issue(category=IssueCategory.how_to_guidance)],
        sentiment=Sentiment.neutral,
        urgency=Urgency.low,
        business_impact=BusinessImpact.none,
        escalation_signal=True,
    )
    decision = route(understanding, EnrichmentResult(tier=CustomerTier.pro))

    assert decision.human_review_required is True
    assert EscalationLevel.tier2 in decision.escalations
    assert decision.next_action is not NextAction.auto_resolve_with_kb
    assert "M4" in decision.rules_fired
