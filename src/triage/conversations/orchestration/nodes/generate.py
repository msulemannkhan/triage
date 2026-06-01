"""Generate — write the customer reply + internal summary (LLM, prose only).

Resolving the turn also resets the clarification counter: the max-turns guard is
per clarification *episode*, so a returning conversation that once asked a
question isn't penalised on its next, unrelated message.
"""

from triage.conversations.models.enums import ConversationStatus
from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger
from triage.providers.llm.base import LLMProvider

_log = get_logger("orchestration")


def make_generate_node(llm: LLMProvider):
    async def generate_node(state: GraphState) -> dict:
        assert state.understanding is not None and state.enrichment is not None
        assert state.decision is not None
        output = await llm.write_response(state.understanding, state.enrichment, state.decision)
        _log.info(
            "node_generate",
            node="generate",
            status=ConversationStatus.resolved.value,
            reply_chars=len(output.customer_reply),
            summary_chars=len(output.internal_summary),
        )
        return {
            "generated": output,
            "status": ConversationStatus.resolved,
            "clarification_count": 0,
        }

    return generate_node
