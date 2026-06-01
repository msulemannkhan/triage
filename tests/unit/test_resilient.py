"""M12: ResilientLLMProvider degrades gracefully when the inner provider fails."""

from triage.conversations.models.enums import (
    BusinessImpact,
    CustomerTier,
    IssueCategory,
    NextAction,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import (
    EnrichmentResult,
    GeneratedOutput,
    Issue,
    RoutingDecision,
    Understanding,
)
from triage.providers.llm.base import LLMProvider
from triage.providers.llm.resilient import ResilientLLMProvider

_U = Understanding(
    issues=[Issue(category=IssueCategory.mobile_app)],
    sentiment=Sentiment.neutral,
    urgency=Urgency.normal,
    business_impact=BusinessImpact.none,
)


class _FailingProvider(LLMProvider):
    async def understand(self, message, prior=None):
        raise RuntimeError("boom")

    async def clarify(self, understanding):
        raise RuntimeError("boom")

    async def tie_break(self, candidates, understanding):
        raise RuntimeError("boom")

    async def write_response(self, understanding, enrichment, decision):
        raise RuntimeError("boom")


async def test_understand_degrades_to_unknown():
    provider = ResilientLLMProvider(_FailingProvider())
    u = await provider.understand("anything")
    assert u.issues[0].category is IssueCategory.other


async def test_tie_break_falls_back_to_first_candidate():
    provider = ResilientLLMProvider(_FailingProvider())
    chosen = await provider.tie_break([Team.platform_sre, Team.billing_ops], _U)
    assert chosen is Team.platform_sre


async def test_clarify_and_write_response_return_templated_fallbacks():
    provider = ResilientLLMProvider(_FailingProvider())
    assert isinstance(await provider.clarify(_U), str)
    decision = RoutingDecision(
        primary_owner=Team.tier1_support,
        next_action=NextAction.route_to_queue,
        effective_urgency=Urgency.normal,
        effective_business_impact=BusinessImpact.low,
    )
    out = await provider.write_response(_U, EnrichmentResult(tier=CustomerTier.free), decision)
    assert isinstance(out, GeneratedOutput)
    assert out.customer_reply
