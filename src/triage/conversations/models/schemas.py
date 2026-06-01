"""Typed domain models — the contracts that flow between layers.

These are pure data shapes (no behavior, no I/O). The rules engine consumes
``Understanding`` + ``EnrichmentResult`` and produces a ``RoutingDecision``;
the output stage combines that with generated prose into a ``DecisionPacket``.
"""

from pydantic import BaseModel, Field

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

DECISION_PACKET_SCHEMA_VERSION = "1.0"


class Issue(BaseModel):
    """One distinct problem extracted from a message."""

    category: IssueCategory
    affected_component: AffectedComponent | None = None


class Understanding(BaseModel):
    """Output of the understanding step — message decomposed into structured signals."""

    issues: list[Issue] = Field(min_length=1)
    sentiment: Sentiment
    urgency: Urgency
    business_impact: BusinessImpact
    escalation_signal: bool = False


class EnrichmentResult(BaseModel):
    """Customer context attached by the enrichment step (from the fixture)."""

    tier: CustomerTier
    prior_interactions: int = 0
    related_products: list[str] = Field(default_factory=list)
    affected_components: list[AffectedComponent] = Field(default_factory=list)
    candidate_team: Team | None = None
    known_customer: bool = True


class RoutingDecision(BaseModel):
    """The deterministic outcome of the rules engine — every decision that matters,
    plus the rationale (which rules fired) for the audit log."""

    primary_owner: Team
    secondary_tags: list[Team] = Field(default_factory=list)
    escalations: list[EscalationLevel] = Field(default_factory=list)
    next_action: NextAction
    effective_urgency: Urgency
    effective_business_impact: BusinessImpact
    human_review_required: bool = False
    rules_fired: list[str] = Field(default_factory=list)


class DecisionPacket(BaseModel):
    """The final, schema-versioned output returned to the caller / downstream."""

    schema_version: str = DECISION_PACKET_SCHEMA_VERSION
    routing: RoutingDecision
    customer_reply: str
    internal_summary: str


class GeneratedOutput(BaseModel):
    """The natural-language output the LLM produces — prose only, no decisions."""

    customer_reply: str
    internal_summary: str


class AuditEntry(BaseModel):
    """An append-only record of one turn's outcome — the audit trail. The
    ``decision.rules_fired`` list is the rationale for why the system acted."""

    conversation_id: str
    customer_id: str
    status: ConversationStatus
    decision: RoutingDecision | None = None
    clarification: str | None = None


class Customer(BaseModel):
    """A record in the (mocked) customer fixture."""

    customer_id: str
    tier: CustomerTier
    prior_interactions: int = 0
    related_products: list[str] = Field(default_factory=list)
