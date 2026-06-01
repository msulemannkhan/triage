"""The routing & escalation policy, expressed deterministically.

``route()`` is the coordinator: it applies the reconciliation, escalation rules
(R1–R4), modifiers (M1–M4), and the auto-resolve rule (A1) in a fixed order,
recording which rules fired for the audit trail. Pure: same input → same output.
"""

from triage.conversations.models.enums import (
    BusinessImpact,
    CustomerTier,
    EscalationLevel,
    IssueCategory,
    NextAction,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import (
    EnrichmentResult,
    RoutingDecision,
    Understanding,
)

from .reconcile import owners

_REPEAT_CONTACT_THRESHOLD = 2


def _bump(urgency: Urgency) -> Urgency:
    order = list(Urgency)
    return order[min(urgency.rank + 1, len(order) - 1)]


def _add(escalations: list[EscalationLevel], level: EscalationLevel) -> None:
    if level not in escalations:
        escalations.append(level)


def route(understanding: Understanding, enrichment: EnrichmentResult) -> RoutingDecision:
    fired: list[str] = []
    urgency = understanding.urgency
    impact = understanding.business_impact
    categories = {issue.category for issue in understanding.issues}
    escalations: list[EscalationLevel] = []
    human_review = False

    # M1 — repeat contact bumps urgency one level.
    if enrichment.prior_interactions >= _REPEAT_CONTACT_THRESHOLD:
        urgency = _bump(urgency)
        fired.append("M1")

    # R1 — platform outage OR high+ business impact -> on-call engineering.
    if IssueCategory.platform_outage in categories or impact >= BusinessImpact.high:
        _add(escalations, EscalationLevel.on_call_engineering)
        fired.append("R1")

    # R2 — enterprise tier AND high+ urgency -> notify the account manager (in parallel).
    if enrichment.tier is CustomerTier.enterprise and urgency >= Urgency.high:
        _add(escalations, EscalationLevel.account_manager)
        fired.append("R2")

    # R3 — billing issue with medium+ impact -> tier-2.
    if IssueCategory.billing_payments in categories and impact >= BusinessImpact.medium:
        _add(escalations, EscalationLevel.tier2)
        fired.append("R3")

    # R4 — data/privacy is always compliance-sensitive -> tier-2.
    if IssueCategory.data_export_privacy in categories:
        _add(escalations, EscalationLevel.tier2)
        fired.append("R4")

    # M4 — explicit escalation request: the LLM signals, this rule decides.
    if understanding.escalation_signal:
        _add(escalations, EscalationLevel.tier2)
        human_review = True
        fired.append("M4")

    # M2 — angry + repeat contact -> always a human, never auto-resolve.
    if (
        understanding.sentiment is Sentiment.angry
        and enrichment.prior_interactions >= _REPEAT_CONTACT_THRESHOLD
    ):
        human_review = True
        fired.append("M2")

    # M3 — critical urgency -> always a human in the loop.
    if urgency is Urgency.critical:
        human_review = True
        fired.append("M3")

    next_action = _next_action(understanding, urgency, escalations, human_review, fired)
    primary_owner, secondary_tags = owners(understanding.issues)

    return RoutingDecision(
        primary_owner=primary_owner,
        secondary_tags=secondary_tags,
        escalations=escalations,
        next_action=next_action,
        effective_urgency=urgency,
        effective_business_impact=impact,
        human_review_required=human_review,
        rules_fired=fired,
    )


def _next_action(
    understanding: Understanding,
    urgency: Urgency,
    escalations: list[EscalationLevel],
    human_review: bool,
    fired: list[str],
) -> NextAction:
    if EscalationLevel.on_call_engineering in escalations:
        return NextAction.create_incident
    if EscalationLevel.account_manager in escalations:
        return NextAction.notify_account_manager
    # A1 — deflect only a calm, single, low-urgency how-to with nothing else going on.
    if (
        not escalations
        and not human_review
        and len(understanding.issues) == 1
        and understanding.issues[0].category is IssueCategory.how_to_guidance
        and urgency <= Urgency.normal
        and understanding.sentiment in (Sentiment.positive, Sentiment.neutral)
    ):
        fired.append("A1")
        return NextAction.auto_resolve_with_kb
    return NextAction.route_to_queue
