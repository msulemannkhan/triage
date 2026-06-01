"""A seeded, deterministic customer fixture (50+ records).

Generation is fully deterministic (no randomness) so the fixture is reproducible
across runs. The named personas referenced in the design walkthroughs are added
as fixed entries.
"""

from triage.conversations.models.enums import CustomerTier
from triage.conversations.models.schemas import Customer

from .customer_repository import CustomerRepository


def _build_fixture() -> dict[str, Customer]:
    tiers = list(CustomerTier)
    customers: dict[str, Customer] = {}
    for i in range(50):
        customer_id = f"cust_{1000 + i}"
        products = ["web"]
        if i % 2 == 0:
            products.append("mobile")
        if i % 3 == 0:
            products.append("billing")
        if i % 5 == 0:
            products.append("api")
        customers[customer_id] = Customer(
            customer_id=customer_id,
            tier=tiers[i % len(tiers)],
            prior_interactions=i % 4,
            related_products=products,
        )

    # Named personas from the design walkthroughs (fixed for reproducibility).
    customers["cust_4821"] = Customer(
        customer_id="cust_4821",
        tier=CustomerTier.enterprise,
        prior_interactions=2,
        related_products=["web", "mobile", "billing"],
    )
    customers["cust_2290"] = Customer(
        customer_id="cust_2290",
        tier=CustomerTier.pro,
        prior_interactions=0,
        related_products=["web", "api"],
    )
    return customers


class SeededCustomerRepository(CustomerRepository):
    def __init__(self) -> None:
        self._customers = _build_fixture()

    def get(self, customer_id: str) -> Customer | None:
        return self._customers.get(customer_id)

    def __len__(self) -> int:
        return len(self._customers)
