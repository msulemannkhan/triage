"""M1: typed domain models validate and round-trip as expected."""

import pytest
from pydantic import ValidationError

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    NextAction,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import (
    DECISION_PACKET_SCHEMA_VERSION,
    DecisionPacket,
    Issue,
    RoutingDecision,
    Understanding,
)


def _routing() -> RoutingDecision:
    return RoutingDecision(
        primary_owner=Team.platform_sre,
        next_action=NextAction.create_incident,
        effective_urgency=Urgency.high,
        effective_business_impact=BusinessImpact.high,
    )


def test_understanding_requires_at_least_one_issue():
    with pytest.raises(ValidationError):
        Understanding(
            issues=[],
            sentiment=Sentiment.neutral,
            urgency=Urgency.low,
            business_impact=BusinessImpact.none,
        )


def test_understanding_accepts_multiple_issues():
    u = Understanding(
        issues=[
            Issue(category=IssueCategory.mobile_app),
            Issue(category=IssueCategory.billing_payments),
        ],
        sentiment=Sentiment.frustrated,
        urgency=Urgency.high,
        business_impact=BusinessImpact.high,
        escalation_signal=True,
    )
    assert len(u.issues) == 2


def test_routing_decision_defaults():
    r = _routing()
    assert r.escalations == []
    assert r.secondary_tags == []
    assert r.human_review_required is False
    assert r.rules_fired == []


def test_decision_packet_versioned_and_json_round_trips():
    packet = DecisionPacket(
        routing=_routing(),
        customer_reply="We're on it.",
        internal_summary="Enterprise outage, escalated.",
    )
    assert packet.schema_version == DECISION_PACKET_SCHEMA_VERSION

    raw = packet.model_dump_json()
    assert '"schema_version":"1.0"' in raw
    # enum values serialize as their string form
    assert '"primary_owner":"platform_sre"' in raw

    restored = DecisionPacket.model_validate_json(raw)
    assert restored == packet
