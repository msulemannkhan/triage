"""Enrich — attach customer context (deterministic lookup, no LLM)."""

from collections.abc import Callable

from triage.conversations.models.schemas import EnrichmentResult
from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger

EnrichFn = Callable[[str], EnrichmentResult]

_log = get_logger("orchestration")


def make_enrich_node(enrich: EnrichFn):
    async def enrich_node(state: GraphState) -> dict:
        result = enrich(state.customer_id)
        _log.info(
            "node_enrich",
            node="enrich",
            known_customer=result.known_customer,
            tier=result.tier.value,
            prior_interactions=result.prior_interactions,
            candidate_team=result.candidate_team.value if result.candidate_team else None,
        )
        return {"enrichment": result}

    return enrich_node
