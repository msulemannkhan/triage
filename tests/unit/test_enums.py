"""M1: controlled vocabularies — ordering, serialization, completeness."""

from triage.conversations.models.enums import (
    DEFAULT_TEAM_BY_CATEGORY,
    AffectedComponent,
    BusinessImpact,
    IssueCategory,
    Urgency,
)


def test_urgency_is_ordered_by_severity():
    assert Urgency.low < Urgency.normal < Urgency.high < Urgency.critical
    assert Urgency.critical > Urgency.high
    assert max([Urgency.low, Urgency.high, Urgency.normal]) is Urgency.high


def test_business_impact_is_ordered_by_severity():
    assert BusinessImpact.none < BusinessImpact.low < BusinessImpact.medium
    assert BusinessImpact.severe > BusinessImpact.high
    assert (
        max([BusinessImpact.low, BusinessImpact.severe, BusinessImpact.medium])
        is BusinessImpact.severe
    )


def test_rank_follows_declaration_order():
    assert Urgency.low.rank == 0
    assert Urgency.critical.rank == 3


def test_ordered_enum_still_serializes_as_string():
    # str-enum identity: the member equals its string value
    assert Urgency.high == "high"
    assert Urgency.high.value == "high"


def test_affected_component_uses_hyphenated_values():
    assert AffectedComponent.mobile_app_ios.value == "mobile-app-ios"
    assert AffectedComponent.web_app.value == "web-app"


def test_every_category_has_a_default_team():
    assert set(DEFAULT_TEAM_BY_CATEGORY) == set(IssueCategory)
