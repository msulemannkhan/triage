"""Multi-issue reconciliation — converge a list of issues to one coherent
operational decision: a single primary owner, deduplicated secondary tags, and
detection of when a bounded LLM tie-break is warranted.
"""

from triage.conversations.models.enums import (
    DEFAULT_TEAM_BY_CATEGORY,
    IssueCategory,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import EnrichmentResult, Issue, Understanding

# Declaration order = ascending priority. The last entry is the most severe,
# so it wins when a message contains several issues.
_CATEGORY_PRIORITY: list[IssueCategory] = [
    IssueCategory.other,
    IssueCategory.feature_request,
    IssueCategory.how_to_guidance,
    IssueCategory.account_provisioning,
    IssueCategory.reporting_analytics,
    IssueCategory.mobile_app,
    IssueCategory.api_integrations,
    IssueCategory.authentication,
    IssueCategory.billing_payments,
    IssueCategory.data_export_privacy,
    IssueCategory.platform_outage,
]


def category_priority(category: IssueCategory) -> int:
    return _CATEGORY_PRIORITY.index(category)


def team_for(category: IssueCategory) -> Team:
    return DEFAULT_TEAM_BY_CATEGORY[category]


def owners(issues: list[Issue]) -> tuple[Team, list[Team]]:
    """Return (primary_owner, secondary_tags). The primary is the team of the
    highest-priority issue; secondaries are the other issues' teams, deduplicated
    and in descending-priority order."""
    ordered = sorted(issues, key=lambda i: category_priority(i.category), reverse=True)
    primary = team_for(ordered[0].category)
    secondary: list[Team] = []
    seen = {primary}
    for issue in ordered[1:]:
        team = team_for(issue.category)
        if team not in seen:
            secondary.append(team)
            seen.add(team)
    return primary, secondary


def tie_break_candidates(
    understanding: Understanding, enrichment: EnrichmentResult
) -> list[Team] | None:
    """Detect a genuine, non-critical routing ambiguity worth a bounded LLM
    tie-break: the primary issue's default team and the enrichment-suggested team
    disagree. Returns the candidate set (for the LLM to pick from) or ``None``.

    Never fires for critical urgency — criticals are never tie-broken by the LLM.
    """
    if understanding.urgency is Urgency.critical:
        return None
    if enrichment.candidate_team is None:
        return None
    primary, _ = owners(understanding.issues)
    if enrichment.candidate_team == primary:
        return None
    return sorted({primary, enrichment.candidate_team})
