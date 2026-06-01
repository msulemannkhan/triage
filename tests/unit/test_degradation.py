"""M12: end-to-end graceful degradation — when the LLM fails at every call, the
turn still completes (to a clarification / human), it never crashes."""

from triage.conversations.models.enums import ConversationStatus
from triage.conversations.orchestration.graph import build_graph, run_turn
from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.enrichment import make_enricher
from triage.providers.llm.base import LLMProvider
from triage.providers.llm.resilient import ResilientLLMProvider


class _FailingProvider(LLMProvider):
    async def understand(self, message, prior=None):
        raise RuntimeError("llm down")

    async def clarify(self, understanding):
        raise RuntimeError("llm down")

    async def tie_break(self, candidates, understanding):
        raise RuntimeError("llm down")

    async def write_response(self, understanding, enrichment, decision):
        raise RuntimeError("llm down")


async def test_turn_degrades_to_clarification_when_llm_is_down():
    graph = build_graph(
        ResilientLLMProvider(_FailingProvider()), make_enricher(SeededCustomerRepository())
    )
    state = await run_turn(
        graph, conversation_id="deg-1", customer_id="cust_4821", message="something is wrong"
    )
    # understanding degraded to 'other' -> gate incomplete -> a (templated) clarification.
    assert state.status is ConversationStatus.awaiting_customer
    assert state.clarification is not None
