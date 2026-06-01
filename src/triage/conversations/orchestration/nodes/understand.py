"""Understand — classify the message (LLM, schema-bound), then fold it into any
accumulated understanding from earlier turns and clear a pending question."""

from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger
from triage.providers.llm.base import LLMProvider

from ..merge import merge

_log = get_logger("orchestration")


def make_understand_node(llm: LLMProvider):
    async def understand(state: GraphState) -> dict:
        prior = state.understanding
        fresh = await llm.understand(state.message, prior=prior)
        merged = merge(prior, fresh) if prior is not None else fresh
        resumed = prior is not None
        _log.info(
            "node_understand",
            node="understand",
            resumed=resumed,
            categories=[i.category.value for i in merged.issues],
            sentiment=merged.sentiment.value,
            urgency=merged.urgency.value,
            business_impact=merged.business_impact.value,
            escalation_signal=merged.escalation_signal,
        )
        return {"understanding": merged, "clarification": None}

    return understand
