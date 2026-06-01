"""M13: the eval harness loads the golden set and computes accuracy metrics."""

from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.enrichment import make_enricher
from triage.evaluation import evaluate, load_cases
from triage.providers.llm.heuristic import HeuristicLLMProvider


def test_golden_set_loads_and_is_well_formed():
    cases = load_cases()
    assert len(cases) >= 15
    assert all({"message", "customer_id", "expect_primary_owner", "expect_escalation"} <= c.keys()
               for c in cases)


async def test_evaluate_computes_accuracy_metrics():
    cases = load_cases()
    report = await evaluate(
        cases, HeuristicLLMProvider(), make_enricher(SeededCustomerRepository())
    )
    assert report["n"] == len(cases)
    assert 0.0 <= report["routing_accuracy"] <= 1.0
    assert 0.0 <= report["escalation_accuracy"] <= 1.0
    # the heuristic should get a clear majority of the routing right
    assert report["routing_accuracy"] >= 0.7
