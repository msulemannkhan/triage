"""M3: provider seams — abstract interfaces + deterministic fakes."""

import inspect

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
from triage.providers.llm.fake import FakeLLMProvider
from triage.providers.transcription.base import Transcriber
from triage.providers.transcription.fake import FakeTranscriber


def test_provider_interfaces_are_abstract():
    assert inspect.isabstract(LLMProvider)
    assert inspect.isabstract(Transcriber)


async def test_fake_llm_returns_scripted_understanding():
    scripted = Understanding(
        issues=[Issue(category=IssueCategory.billing_payments)],
        sentiment=Sentiment.frustrated,
        urgency=Urgency.high,
        business_impact=BusinessImpact.high,
    )
    provider = FakeLLMProvider(understanding=scripted)
    assert await provider.understand("billing is broken") is scripted


async def test_fake_llm_default_understanding_is_safe():
    u = await FakeLLMProvider().understand("hello")
    assert u.issues[0].category is IssueCategory.other


async def test_fake_tie_break_prefers_choice_then_falls_back_to_first():
    candidates = [Team.mobile_engineering, Team.platform_sre]
    u = await FakeLLMProvider().understand("x")

    chooser = FakeLLMProvider(tie_break_choice=Team.platform_sre)
    assert await chooser.tie_break(candidates, u) is Team.platform_sre
    assert await FakeLLMProvider().tie_break(candidates, u) is Team.mobile_engineering


async def test_fake_write_response_is_prose_mentioning_the_owner():
    provider = FakeLLMProvider()
    u = await provider.understand("x")
    decision = RoutingDecision(
        primary_owner=Team.billing_ops,
        next_action=NextAction.route_to_queue,
        effective_urgency=Urgency.normal,
        effective_business_impact=BusinessImpact.low,
    )
    out = await provider.write_response(u, EnrichmentResult(tier=CustomerTier.pro), decision)
    assert isinstance(out, GeneratedOutput)
    assert "billing_ops" in out.internal_summary


async def test_fake_transcriber_returns_preset():
    assert await FakeTranscriber("hello world").transcribe(b"...") == "hello world"
