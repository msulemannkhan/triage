"""Multi-turn state merge — fold a new turn's understanding into the accumulated
one so a conversation grows context instead of forgetting it.

Pure and deterministic: real issues supersede the ``other`` placeholder, severity
takes the max across turns, sentiment reflects the latest message, and an
escalation request once raised stays raised.
"""

from triage.conversations.models.enums import IssueCategory
from triage.conversations.models.schemas import Issue, Understanding


def _merge_issues(prior: list[Issue], new: list[Issue]) -> list[Issue]:
    combined: list[Issue] = []
    seen: set[IssueCategory] = set()
    for issue in [*prior, *new]:
        if issue.category not in seen:
            combined.append(issue)
            seen.add(issue.category)
    real = [issue for issue in combined if issue.category is not IssueCategory.other]
    return real or combined


def merge(prior: Understanding, new: Understanding) -> Understanding:
    return Understanding(
        issues=_merge_issues(prior.issues, new.issues),
        sentiment=new.sentiment,
        urgency=max(prior.urgency, new.urgency),
        business_impact=max(prior.business_impact, new.business_impact),
        escalation_signal=prior.escalation_signal or new.escalation_signal,
    )
