"""M5: the enricher maps customers to enrichment context, with safe defaults."""

from triage.conversations.models.enums import AffectedComponent, CustomerTier, Team
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)
from triage.conversations.services.enrichment import _candidate_team, make_enricher


def test_known_customer_enriches_with_context():
    enrich = make_enricher(SeededCustomerRepository())
    result = enrich("cust_4821")

    assert result.known_customer is True
    assert result.tier is CustomerTier.enterprise
    assert result.prior_interactions == 2
    # products map to affected components
    assert AffectedComponent.billing_service in result.affected_components
    assert AffectedComponent.web_app in result.affected_components


def test_unknown_customer_degrades_to_safe_defaults():
    enrich = make_enricher(SeededCustomerRepository())
    result = enrich("ghost")

    assert result.known_customer is False
    assert result.tier is CustomerTier.free
    assert result.prior_interactions == 0
    assert result.related_products == []
    assert result.affected_components == []


def test_components_are_deduplicated():
    enrich = make_enricher(SeededCustomerRepository())
    result = enrich("cust_4821")  # web + mobile + billing
    assert len(result.affected_components) == len(set(result.affected_components))


def test_candidate_team_is_set_for_a_single_specialist_customer():
    # A focused profile (one specialist product) yields a candidate the tie-break
    # can weigh against the message-derived primary owner.
    assert _candidate_team(["web", "api"]) is Team.api_integrations_team
    assert _candidate_team(["web", "mobile"]) is Team.mobile_engineering
    assert _candidate_team(["billing"]) is Team.billing_ops


def test_candidate_team_is_none_when_ambiguous_or_unspecialised():
    # Multiple specialists -> no single candidate; web-only -> no specialist.
    assert _candidate_team(["web", "mobile", "billing"]) is None
    assert _candidate_team(["web"]) is None
    assert _candidate_team([]) is None


def test_enricher_populates_candidate_team_so_tie_break_is_live():
    enrich = make_enricher(SeededCustomerRepository())
    # cust_2290 is web + api -> a single specialist (api), so the path is reachable.
    assert enrich("cust_2290").candidate_team is Team.api_integrations_team
    # cust_4821 spans mobile + billing -> ambiguous, no candidate.
    assert enrich("cust_4821").candidate_team is None
