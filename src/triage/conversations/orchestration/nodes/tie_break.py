"""Tie-break — the single, bounded place the LLM influences a (non-critical)
routing decision: it picks the primary owner from a provided candidate set."""

from triage.conversations.decision.reconcile import tie_break_candidates
from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger
from triage.providers.llm.base import LLMProvider

_log = get_logger("orchestration")


def make_tie_break_node(llm: LLMProvider):
    async def tie_break_node(state: GraphState) -> dict:
        assert state.understanding is not None and state.enrichment is not None
        assert state.decision is not None
        candidates = tie_break_candidates(state.understanding, state.enrichment)
        assert candidates is not None  # only reached when a tie exists
        previous = state.decision.primary_owner
        choice = await llm.tie_break(candidates, state.understanding)
        _log.info(
            "node_tie_break",
            node="tie_break",
            candidates=[t.value for t in candidates],
            previous_owner=previous.value,
            chosen_owner=choice.value,
            changed=choice != previous,
        )
        updated = state.decision.model_copy(
            update={
                "primary_owner": choice,
                "rules_fired": [*state.decision.rules_fired, "T1"],
            }
        )
        return {"decision": updated}

    return tie_break_node
