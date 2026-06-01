"""The completeness gate — decides whether we know enough to route safely,
and how many clarifying questions we're allowed before handing off to a human.

Pure functions over structured signals; the orchestration layer turns these
answers into graph transitions.
"""

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import EnrichmentResult, Understanding


def is_complete(understanding: Understanding, enrichment: EnrichmentResult) -> bool:
    """C1 — we can route only if there is at least one routable (non-``other``)
    issue AND we have enough context (the customer is known, or the message
    itself conveys business impact)."""
    has_routable_issue = any(
        issue.category is not IssueCategory.other for issue in understanding.issues
    )
    context_known = (
        enrichment.known_customer
        or understanding.business_impact is not BusinessImpact.none
    )
    return has_routable_issue and context_known


def effective_clarification_cap(
    understanding: Understanding, base_cap: int, sensitive_cap: int
) -> int:
    """The max-turns guard. Angry sentiment or critical urgency reduces the cap —
    escalate to a human sooner rather than interrogate a frustrated customer."""
    sensitive = (
        understanding.sentiment is Sentiment.angry or understanding.urgency is Urgency.critical
    )
    return sensitive_cap if sensitive else base_cap
