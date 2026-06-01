"""Enrichment — turn a customer record into the context the pipeline needs.

``make_enricher`` binds a repository and returns the plain ``str -> EnrichmentResult``
function the graph's enrich node expects. An unknown customer degrades to safe
defaults (free tier, no history) rather than failing.

It also derives a ``candidate_team`` — an alternative owning-team hypothesis based
purely on *who the customer is* (their product footprint), independent of the
message. The reconciliation layer fires the bounded LLM tie-break only when this
disagrees with the message-derived primary owner, so a focused single-product
customer's specialist can be weighed against the literal classification.
"""

from collections.abc import Callable

from triage.conversations.models.enums import AffectedComponent, CustomerTier, Team
from triage.conversations.models.schemas import EnrichmentResult

from ..repositories.customer_repository import CustomerRepository

_COMPONENTS_BY_PRODUCT: dict[str, list[AffectedComponent]] = {
    "web": [AffectedComponent.web_app],
    "mobile": [AffectedComponent.mobile_app_ios, AffectedComponent.mobile_app_android],
    "billing": [AffectedComponent.billing_service],
    "api": [AffectedComponent.api_gateway],
}

# Specialist team implied by a product. "web" has no specialist owner, so it
# never contributes a candidate.
_TEAM_BY_PRODUCT: dict[str, Team] = {
    "mobile": Team.mobile_engineering,
    "billing": Team.billing_ops,
    "api": Team.api_integrations_team,
}


def _components_for(products: list[str]) -> list[AffectedComponent]:
    components: list[AffectedComponent] = []
    for product in products:
        for component in _COMPONENTS_BY_PRODUCT.get(product, []):
            if component not in components:
                components.append(component)
    return components


def _candidate_team(products: list[str]) -> Team | None:
    """A candidate owner from the customer's footprint — but only when it's
    unambiguous: exactly one specialist product. Multi-specialist (or web-only)
    customers yield no candidate, so the tie-break stays rare and meaningful."""
    specialists = list(
        dict.fromkeys(_TEAM_BY_PRODUCT[p] for p in products if p in _TEAM_BY_PRODUCT)
    )
    return specialists[0] if len(specialists) == 1 else None


def make_enricher(repo: CustomerRepository) -> Callable[[str], EnrichmentResult]:
    def enrich(customer_id: str) -> EnrichmentResult:
        customer = repo.get(customer_id)
        if customer is None:
            return EnrichmentResult(tier=CustomerTier.free, known_customer=False)
        return EnrichmentResult(
            tier=customer.tier,
            prior_interactions=customer.prior_interactions,
            related_products=customer.related_products,
            affected_components=_components_for(customer.related_products),
            candidate_team=_candidate_team(customer.related_products),
            known_customer=True,
        )

    return enrich
