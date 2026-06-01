"""A keyword-heuristic LLM provider for key-less local dev and the demo, until
the real model lands at M11. Fully deterministic; it subclasses the fake to reuse
the clarify / tie-break / write-response behavior and overrides only ``understand``.
"""

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding

from .fake import FakeLLMProvider

_CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], IssueCategory]] = [
    (("login", "sign in", "password", "sso", "mfa"), IssueCategory.authentication),
    (("crash", "app", "mobile", "ios", "android"), IssueCategory.mobile_app),
    (("bill", "charge", "invoice", "payment", "refund"), IssueCategory.billing_payments),
    (("report", "dashboard", "analytics"), IssueCategory.reporting_analytics),
    (("outage", "down", "unavailable", "500"), IssueCategory.platform_outage),
    (("api", "webhook", "integration", "endpoint"), IssueCategory.api_integrations),
    (("export", "gdpr", "privacy", "delete my data"), IssueCategory.data_export_privacy),
    (("how do i", "how to", "guide", "where do i"), IssueCategory.how_to_guidance),
]
_URGENT = ("urgent", "asap", "immediately", "critical", "right now")
_ESCALATE = ("manager", "escalate", "urgent", "unacceptable")
_ANGRY = ("angry", "furious", "unacceptable", "ridiculous")
_FRUSTRATED = ("frustrated", "still", "again", "twice")
_HIGH_IMPACT = ("production", "blocking", "everyone", "all users", "can't work", "cant work")


def _any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


class HeuristicLLMProvider(FakeLLMProvider):
    async def understand(
        self, message: str, prior: Understanding | None = None
    ) -> Understanding:
        text = message.lower()
        categories = [cat for kws, cat in _CATEGORY_KEYWORDS if _any(text, kws)]
        if not categories:
            categories = [IssueCategory.other]
        issues = [Issue(category=c) for c in dict.fromkeys(categories)]

        if _any(text, _ANGRY):
            sentiment = Sentiment.angry
        elif _any(text, _FRUSTRATED):
            sentiment = Sentiment.frustrated
        else:
            sentiment = Sentiment.neutral

        urgency = Urgency.high if _any(text, _URGENT) else Urgency.normal
        if _any(text, _HIGH_IMPACT):
            impact = BusinessImpact.high
        elif categories != [IssueCategory.other]:
            impact = BusinessImpact.medium
        else:
            impact = BusinessImpact.none

        return Understanding(
            issues=issues,
            sentiment=sentiment,
            urgency=urgency,
            business_impact=impact,
            escalation_signal=_any(text, _ESCALATE),
        )
