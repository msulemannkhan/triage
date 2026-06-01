"""M2: multi-issue reconciliation and tie-break detection."""

from triage.conversations.decision.reconcile import (
    category_priority,
    owners,
    tie_break_candidates,
)
from triage.conversations.models.enums import (
    BusinessImpact,
    CustomerTier,
    IssueCategory,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import EnrichmentResult, Issue, Understanding


def test_outage_is_highest_priority():
    assert category_priority(IssueCategory.platform_outage) > category_priority(
        IssueCategory.billing_payments
    )
    assert category_priority(IssueCategory.billing_payments) > category_priority(
        IssueCategory.how_to_guidance
    )


def test_owners_picks_highest_priority_as_primary_and_dedups_secondary():
    issues = [
        Issue(category=IssueCategory.mobile_app),
        Issue(category=IssueCategory.billing_payments),
        Issue(category=IssueCategory.reporting_analytics),
    ]
    primary, secondary = owners(issues)
    assert primary is Team.billing_ops  # billing has the highest priority here
    assert Team.mobile_engineering in secondary
    assert Team.data_reporting in secondary
    assert Team.billing_ops not in secondary  # not duplicated


def _understanding(category, urgency=Urgency.high) -> Understanding:
    return Understanding(
        issues=[Issue(category=category)],
        sentiment=Sentiment.neutral,
        urgency=urgency,
        business_impact=BusinessImpact.medium,
    )


def test_tie_break_fires_when_candidate_team_disagrees():
    u = _understanding(IssueCategory.mobile_app)  # default team: mobile_engineering
    e = EnrichmentResult(tier=CustomerTier.pro, candidate_team=Team.platform_sre)
    candidates = tie_break_candidates(u, e)
    assert candidates is not None
    assert set(candidates) == {Team.mobile_engineering, Team.platform_sre}


def test_no_tie_break_when_candidate_agrees_or_absent():
    u = _understanding(IssueCategory.mobile_app)
    assert tie_break_candidates(u, EnrichmentResult(tier=CustomerTier.pro)) is None
    agree = EnrichmentResult(tier=CustomerTier.pro, candidate_team=Team.mobile_engineering)
    assert tie_break_candidates(u, agree) is None


def test_no_tie_break_for_critical():
    u = _understanding(IssueCategory.mobile_app, urgency=Urgency.critical)
    e = EnrichmentResult(tier=CustomerTier.pro, candidate_team=Team.platform_sre)
    assert tie_break_candidates(u, e) is None
