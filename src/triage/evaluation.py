"""Offline evaluation harness.

Runs labeled golden-set scenarios through the pipeline (understand → enrich →
rules) and scores routing + escalation accuracy. Runs against any LLM provider —
the key-less heuristic by default, or a real model when configured — so it works
in CI deterministically and can measure the real model on demand.
"""

import pathlib
from collections.abc import Callable

from triage.conversations.decision.rules import route
from triage.conversations.models.schemas import EnrichmentResult
from triage.providers.llm.base import LLMProvider

_DEFAULT_GOLDEN = pathlib.Path(__file__).parents[2] / "eval" / "golden_set.yaml"


def load_cases(path: pathlib.Path = _DEFAULT_GOLDEN) -> list[dict]:
    import yaml  # lazy: pyyaml is only needed to run the eval

    return yaml.safe_load(path.read_text())


async def evaluate(
    cases: list[dict],
    provider: LLMProvider,
    enrich: Callable[[str], EnrichmentResult],
) -> dict:
    rows: list[dict] = []
    for case in cases:
        understanding = await provider.understand(case["message"])
        decision = route(understanding, enrich(case["customer_id"]))
        rows.append(
            {
                "message": case["message"][:48],
                "expected": case["expect_primary_owner"],
                "got": decision.primary_owner.value,
                "owner_ok": decision.primary_owner.value == case["expect_primary_owner"],
                "esc_ok": (len(decision.escalations) > 0) == case["expect_escalation"],
            }
        )
    n = len(rows) or 1
    return {
        "n": len(rows),
        "routing_accuracy": sum(r["owner_ok"] for r in rows) / n,
        "escalation_accuracy": sum(r["esc_ok"] for r in rows) / n,
        "rows": rows,
    }
