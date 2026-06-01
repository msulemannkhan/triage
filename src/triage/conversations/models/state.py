"""The graph's conversation state — what flows between orchestration nodes.

For now (single-pass), nodes overwrite their slots. Multi-turn accumulation
(merging successive turns) arrives at M6 via channel reducers.
"""

from pydantic import BaseModel

from .enums import ConversationStatus
from .schemas import EnrichmentResult, GeneratedOutput, RoutingDecision, Understanding


class GraphState(BaseModel):
    conversation_id: str
    customer_id: str
    message: str

    understanding: Understanding | None = None
    enrichment: EnrichmentResult | None = None
    decision: RoutingDecision | None = None
    generated: GeneratedOutput | None = None
    clarification: str | None = None

    clarification_count: int = 0
    status: ConversationStatus = ConversationStatus.active
