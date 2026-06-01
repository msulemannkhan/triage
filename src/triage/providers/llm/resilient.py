"""Resilience wrapper for the LLM seam — graceful degradation (NFR-2).

Wraps any provider so a failure degrades instead of crashing a turn:
understanding falls back to 'unknown' (which routes to clarification / a human),
prose falls back to templates, tie-break to the first candidate. This is also the
universal observability choke point for the LLM: every call is timed here and
logged with its outcome (``duration_ms`` + degraded?), regardless of which inner
provider (heuristic / openai) runs. (Transport-level retries/backoff are handled
by the OpenAI SDK and arq.)
"""

from collections.abc import Sequence
from time import perf_counter

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
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
from triage.core.logging import get_logger, ms_since

from .base import LLMProvider

_log = get_logger("llm")


class ResilientLLMProvider(LLMProvider):
    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner
        self._name = type(inner).__name__

    async def understand(
        self, message: str, prior: Understanding | None = None
    ) -> Understanding:
        start = perf_counter()
        try:
            result = await self._inner.understand(message, prior)
        except Exception as exc:  # noqa: BLE001 — degrade, don't crash the turn
            _log.warning(
                "llm_understand_degraded",
                provider=self._name,
                duration_ms=ms_since(start),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return Understanding(
                issues=[Issue(category=IssueCategory.other)],
                sentiment=Sentiment.neutral,
                urgency=Urgency.normal,
                business_impact=BusinessImpact.none,
            )
        _log.debug(
            "llm_understand",
            provider=self._name,
            duration_ms=ms_since(start),
            categories=[i.category.value for i in result.issues],
        )
        return result

    async def clarify(self, understanding: Understanding) -> str:
        start = perf_counter()
        try:
            result = await self._inner.clarify(understanding)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "llm_clarify_degraded",
                provider=self._name,
                duration_ms=ms_since(start),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return "Could you share a few more details so we can route this correctly?"
        _log.debug("llm_clarify", provider=self._name, duration_ms=ms_since(start))
        return result

    async def tie_break(self, candidates: Sequence[Team], understanding: Understanding) -> Team:
        start = perf_counter()
        try:
            result = await self._inner.tie_break(list(candidates), understanding)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "llm_tie_break_degraded",
                provider=self._name,
                duration_ms=ms_since(start),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return candidates[0]
        _log.debug(
            "llm_tie_break",
            provider=self._name,
            duration_ms=ms_since(start),
            chosen=result.value,
        )
        return result

    async def write_response(
        self,
        understanding: Understanding,
        enrichment: EnrichmentResult,
        decision: RoutingDecision,
    ) -> GeneratedOutput:
        start = perf_counter()
        try:
            result = await self._inner.write_response(understanding, enrichment, decision)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "llm_write_response_degraded",
                provider=self._name,
                duration_ms=ms_since(start),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            reply = "Thanks for reaching out — we've logged your request and we're on it."
            return GeneratedOutput(
                customer_reply=reply,
                internal_summary=(
                    f"Routed to {decision.primary_owner.value}; "
                    f"urgency {decision.effective_urgency.value}. "
                    "(LLM prose unavailable; templated fallback.)"
                ),
            )
        _log.debug("llm_write_response", provider=self._name, duration_ms=ms_since(start))
        return result
