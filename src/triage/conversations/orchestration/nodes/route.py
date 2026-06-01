"""Route — the deterministic rules engine. No LLM; this owns the decisions.

If the gate force-routed an under-specified conversation (clarification budget
exhausted), this applies the safe fallback: hand to tier-1 with human review,
rather than guess.
"""

from triage.conversations.decision.completeness import is_complete
from triage.conversations.decision.rules import route
from triage.conversations.models.enums import NextAction, Team
from triage.conversations.models.schemas import RoutingDecision
from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger

_log = get_logger("orchestration")


def make_route_node():
    async def route_node(state: GraphState) -> dict:
        assert state.understanding is not None and state.enrichment is not None
        if is_complete(state.understanding, state.enrichment):
            decision = route(state.understanding, state.enrichment)
        else:
            decision = RoutingDecision(
                primary_owner=Team.tier1_support,
                next_action=NextAction.route_to_queue,
                effective_urgency=state.understanding.urgency,
                effective_business_impact=state.understanding.business_impact,
                human_review_required=True,
                rules_fired=["GATE_EXHAUSTED"],
            )
        _log.info(
            "node_route",
            node="route",
            primary_owner=decision.primary_owner.value,
            secondary_tags=[t.value for t in decision.secondary_tags],
            escalations=[e.value for e in decision.escalations],
            next_action=decision.next_action.value,
            effective_urgency=decision.effective_urgency.value,
            human_review_required=decision.human_review_required,
            rules_fired=decision.rules_fired,
        )
        return {"decision": decision}

    return route_node
