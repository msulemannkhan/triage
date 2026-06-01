"""Clarify — ask one focused question and pause the turn (LLM, prose only)."""

from triage.conversations.models.enums import ConversationStatus
from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger
from triage.providers.llm.base import LLMProvider

_log = get_logger("orchestration")


def make_clarify_node(llm: LLMProvider):
    async def clarify_node(state: GraphState) -> dict:
        assert state.understanding is not None
        question = await llm.clarify(state.understanding)
        next_count = state.clarification_count + 1
        _log.info(
            "node_clarify",
            node="clarify",
            clarification_count=next_count,
            status=ConversationStatus.awaiting_customer.value,
        )
        return {
            "clarification": question,
            "clarification_count": next_count,
            "status": ConversationStatus.awaiting_customer,
        }

    return clarify_node
