"""Assembly of the LangGraph orchestration graph.

A turn flows: understand -> enrich -> (gate) -> route -> (tie-break?) -> generate.
The gate sends an under-specified message to clarify (pausing the turn with a
question) until the clarification budget is exhausted, after which it force-routes
to a human. Edges (control flow) are deterministic Python; the LLM runs only in nodes.

State persists via a checkpointer keyed by conversation_id, so a follow-up turn
resumes the thread with accumulated context (in-memory here; Postgres at M8).
"""

from collections.abc import Awaitable, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from triage.conversations.decision.completeness import (
    effective_clarification_cap,
    is_complete,
)
from triage.conversations.decision.reconcile import tie_break_candidates
from triage.conversations.models.enums import (
    AffectedComponent,
    BusinessImpact,
    ConversationStatus,
    CustomerTier,
    EscalationLevel,
    IssueCategory,
    NextAction,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import (
    Customer,
    DecisionPacket,
    EnrichmentResult,
    GeneratedOutput,
    Issue,
    RoutingDecision,
    Understanding,
)
from triage.conversations.models.state import GraphState
from triage.core.logging import get_logger
from triage.providers.llm.base import LLMProvider

from .nodes.clarify import make_clarify_node
from .nodes.enrich import EnrichFn, make_enrich_node
from .nodes.generate import make_generate_node
from .nodes.route import make_route_node
from .nodes.tie_break import make_tie_break_node
from .nodes.understand import make_understand_node

_log = get_logger("orchestration")

# Domain types that travel through the checkpoint. We allowlist them explicitly
# for (de)serialization rather than relying on langgraph's permissive default
# (which warns and will be blocked by a future version) — quieter and safer.
_CHECKPOINT_TYPES = [
    IssueCategory, CustomerTier, Urgency, Sentiment, BusinessImpact, Team,
    AffectedComponent, EscalationLevel, NextAction, ConversationStatus,
    Issue, Understanding, EnrichmentResult, RoutingDecision, GeneratedOutput,
    DecisionPacket, Customer,
]


def _checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=None).with_msgpack_allowlist(
        _CHECKPOINT_TYPES
    )


def _needs_tie_break(state: GraphState) -> str:
    """Deterministic: divert to the bounded LLM tie-break only on a genuine tie of
    a *complete* decision. The under-specified GATE_EXHAUSTED fallback (tier-1 +
    human review) is a safety net and is never second-guessed by the LLM."""
    assert state.understanding is not None and state.enrichment is not None
    if not is_complete(state.understanding, state.enrichment):
        _log.debug("edge_tie_break", node="edge", branch="generate", reason="gate_exhausted")
        return "generate"
    candidates = tie_break_candidates(state.understanding, state.enrichment)
    branch = "tie_break" if candidates is not None else "generate"
    _log.debug(
        "edge_tie_break",
        node="edge",
        branch=branch,
        candidates=[t.value for t in candidates] if candidates else None,
    )
    return branch


def build_graph(
    llm: LLMProvider,
    enrich: EnrichFn,
    *,
    clarification_cap: int = 2,
    clarification_cap_sensitive: int = 1,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Wire and compile the graph with the given (real or fake) dependencies."""

    def gate(state: GraphState) -> str:
        # Deterministic: route if we know enough; else clarify until the budget
        # is exhausted, then force-route (the route node applies the human fallback).
        assert state.understanding is not None and state.enrichment is not None
        if is_complete(state.understanding, state.enrichment):
            _log.debug("edge_gate", node="edge", branch="route", reason="complete")
            return "route"
        cap = effective_clarification_cap(
            state.understanding, clarification_cap, clarification_cap_sensitive
        )
        exhausted = state.clarification_count >= cap
        branch = "route" if exhausted else "clarify"
        _log.debug(
            "edge_gate",
            node="edge",
            branch=branch,
            reason="budget_exhausted" if exhausted else "needs_clarification",
            clarification_count=state.clarification_count,
            cap=cap,
        )
        return branch

    builder = StateGraph(GraphState)
    builder.add_node("understand", make_understand_node(llm))
    builder.add_node("enrich", make_enrich_node(enrich))
    builder.add_node("route", make_route_node())
    builder.add_node("tie_break", make_tie_break_node(llm))
    builder.add_node("generate", make_generate_node(llm))
    builder.add_node("clarify", make_clarify_node(llm))

    builder.add_edge(START, "understand")
    builder.add_edge("understand", "enrich")
    builder.add_conditional_edges("enrich", gate, {"route": "route", "clarify": "clarify"})
    builder.add_conditional_edges(
        "route",
        _needs_tie_break,
        {"tie_break": "tie_break", "generate": "generate"},
    )
    builder.add_edge("tie_break", "generate")
    builder.add_edge("generate", END)
    builder.add_edge("clarify", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver(serde=_checkpoint_serde()))


async def run_turn(
    graph,
    *,
    conversation_id: str,
    customer_id: str,
    message: str,
    on_node: Callable[[str], Awaitable[None]] | None = None,
) -> GraphState:
    """Run one message through the graph, resuming the conversation's thread.

    If ``on_node`` is given, stream node-by-node and invoke it per node (used to
    publish live progress); otherwise run in a single ``ainvoke``.
    """
    config = {"configurable": {"thread_id": conversation_id}}
    payload = {"conversation_id": conversation_id, "customer_id": customer_id, "message": message}
    # Never log the raw body (PII); a length is enough to correlate.
    _log.info("turn_started", streamed=on_node is not None, message_chars=len(message))

    if on_node is None:
        result = await graph.ainvoke(payload, config=config)
        return GraphState.model_validate(result)

    async for chunk in graph.astream(payload, config=config, stream_mode="updates"):
        for node_name in chunk:
            _log.debug("node_streamed", node=node_name)
            await on_node(node_name)
    snapshot = await graph.aget_state(config)
    return GraphState.model_validate(snapshot.values)


def to_packet(state: GraphState) -> DecisionPacket | None:
    """Assemble the final decision packet, or None if the turn paused for clarification."""
    if state.decision is None or state.generated is None:
        return None
    return DecisionPacket(
        routing=state.decision,
        customer_reply=state.generated.customer_reply,
        internal_summary=state.generated.internal_summary,
    )
