"""M5: the seeded customer fixture."""

from triage.conversations.models.enums import CustomerTier
from triage.conversations.repositories.seeded_customer_repository import (
    SeededCustomerRepository,
)


def test_fixture_has_at_least_50_customers():
    assert len(SeededCustomerRepository()) >= 50


def test_known_named_persona_is_present_and_fixed():
    repo = SeededCustomerRepository()
    customer = repo.get("cust_4821")
    assert customer is not None
    assert customer.tier is CustomerTier.enterprise
    assert customer.prior_interactions == 2
    assert "billing" in customer.related_products


def test_generated_customer_is_present():
    customer = SeededCustomerRepository().get("cust_1000")
    assert customer is not None
    assert customer.customer_id == "cust_1000"


def test_unknown_customer_returns_none():
    assert SeededCustomerRepository().get("nope") is None


def test_fixture_is_deterministic():
    a = SeededCustomerRepository().get("cust_1007")
    b = SeededCustomerRepository().get("cust_1007")
    assert a == b
