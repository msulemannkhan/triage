"""M2: the completeness gate and the max-turns cap."""

from triage.conversations.decision.completeness import (
    effective_clarification_cap,
    is_complete,
)
from triage.conversations.models.enums import (
    BusinessImpact,
    CustomerTier,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import EnrichmentResult, Issue, Understanding


def _understanding(category, **kw) -> Understanding:
    return Understanding(
        issues=[Issue(category=category)],
        sentiment=kw.get("sentiment", Sentiment.neutral),
        urgency=kw.get("urgency", Urgency.normal),
        business_impact=kw.get("business_impact", BusinessImpact.none),
    )


def test_complete_when_routable_and_customer_known():
    u = _understanding(IssueCategory.billing_payments)
    e = EnrichmentResult(tier=CustomerTier.pro, known_customer=True)
    assert is_complete(u, e) is True


def test_incomplete_when_only_other_category():
    u = _understanding(IssueCategory.other)
    e = EnrichmentResult(tier=CustomerTier.pro, known_customer=True)
    assert is_complete(u, e) is False


def test_incomplete_when_unknown_customer_and_no_impact():
    u = _understanding(IssueCategory.other, business_impact=BusinessImpact.none)
    e = EnrichmentResult(tier=CustomerTier.free, known_customer=False)
    assert is_complete(u, e) is False


def test_complete_when_unknown_customer_but_message_conveys_impact():
    u = _understanding(IssueCategory.billing_payments, business_impact=BusinessImpact.high)
    e = EnrichmentResult(tier=CustomerTier.free, known_customer=False)
    assert is_complete(u, e) is True


def test_clarification_cap_reduced_for_angry_or_critical():
    angry = _understanding(IssueCategory.billing_payments, sentiment=Sentiment.angry)
    critical = _understanding(IssueCategory.billing_payments, urgency=Urgency.critical)
    calm = _understanding(IssueCategory.billing_payments)

    assert effective_clarification_cap(angry, base_cap=2, sensitive_cap=1) == 1
    assert effective_clarification_cap(critical, base_cap=2, sensitive_cap=1) == 1
    assert effective_clarification_cap(calm, base_cap=2, sensitive_cap=1) == 2
