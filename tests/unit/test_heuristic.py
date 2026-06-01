"""M7: the keyword-heuristic dev provider classifies sensibly (deterministic)."""

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.providers.llm.heuristic import HeuristicLLMProvider


async def test_detects_multiple_categories():
    u = await HeuristicLLMProvider().understand(
        "my mobile app crashes and billing invoices are wrong"
    )
    categories = {i.category for i in u.issues}
    assert IssueCategory.mobile_app in categories
    assert IssueCategory.billing_payments in categories


async def test_urgency_and_escalation_keywords():
    u = await HeuristicLLMProvider().understand("the API is down, I need a manager urgently")
    assert u.urgency is Urgency.high
    assert u.escalation_signal is True


async def test_high_impact_and_sentiment():
    u = await HeuristicLLMProvider().understand(
        "this is unacceptable, production is blocking for everyone"
    )
    assert u.sentiment is Sentiment.angry
    assert u.business_impact is BusinessImpact.high


async def test_unmatched_message_is_other():
    u = await HeuristicLLMProvider().understand("hello there")
    assert u.issues[0].category is IssueCategory.other
    assert u.business_impact is BusinessImpact.none
