"""M6: deterministic multi-turn understanding merge."""

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.merge import merge


def _u(categories, *, sentiment=Sentiment.neutral, urgency=Urgency.normal,
       impact=BusinessImpact.none, escalation=False) -> Understanding:
    return Understanding(
        issues=[Issue(category=c) for c in categories],
        sentiment=sentiment,
        urgency=urgency,
        business_impact=impact,
        escalation_signal=escalation,
    )


def test_real_issue_supersedes_other_placeholder():
    prior = _u([IssueCategory.other])
    new = _u([IssueCategory.billing_payments])
    merged = merge(prior, new)
    categories = {i.category for i in merged.issues}
    assert categories == {IssueCategory.billing_payments}  # 'other' dropped


def test_severity_takes_the_max_across_turns():
    prior = _u([IssueCategory.mobile_app], urgency=Urgency.high, impact=BusinessImpact.medium)
    new = _u([IssueCategory.billing_payments], urgency=Urgency.normal, impact=BusinessImpact.high)
    merged = merge(prior, new)
    assert merged.urgency is Urgency.high
    assert merged.business_impact is BusinessImpact.high


def test_issues_accumulate_and_dedupe():
    prior = _u([IssueCategory.mobile_app])
    new = _u([IssueCategory.billing_payments, IssueCategory.mobile_app])
    merged = merge(prior, new)
    categories = {i.category for i in merged.issues}
    assert categories == {IssueCategory.mobile_app, IssueCategory.billing_payments}


def test_escalation_signal_is_sticky():
    prior = _u([IssueCategory.mobile_app], escalation=True)
    new = _u([IssueCategory.mobile_app], escalation=False)
    assert merge(prior, new).escalation_signal is True


def test_sentiment_reflects_latest_turn():
    prior = _u([IssueCategory.mobile_app], sentiment=Sentiment.neutral)
    new = _u([IssueCategory.mobile_app], sentiment=Sentiment.angry)
    assert merge(prior, new).sentiment is Sentiment.angry
