"""A deterministic, scriptable stand-in for the real LLM.

Inject explicit responses for integration tests; sensible defaults keep the
graph runnable in local dev with no API key. ``understandings`` (a list) scripts
successive turns — each ``understand`` call pops the next one — which is how the
multi-turn tests simulate a clarification then a clear answer.
"""

from collections.abc import Sequence

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

from .base import LLMProvider

_DEFAULT_CLARIFICATION = "Could you share a few more details so I can route this to the right team?"


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        understanding: Understanding | None = None,
        understandings: Sequence[Understanding] | None = None,
        clarification: str = _DEFAULT_CLARIFICATION,
        tie_break_choice: Team | None = None,
        output: GeneratedOutput | None = None,
    ) -> None:
        self._understanding = understanding
        self._understandings = list(understandings) if understandings else []
        self._clarification = clarification
        self._tie_break_choice = tie_break_choice
        self._output = output

    async def understand(
        self, message: str, prior: Understanding | None = None
    ) -> Understanding:
        if self._understandings:
            return self._understandings.pop(0)
        if self._understanding is not None:
            return self._understanding
        return Understanding(
            issues=[Issue(category=IssueCategory.other)],
            sentiment=Sentiment.neutral,
            urgency=Urgency.normal,
            business_impact=BusinessImpact.none,
        )

    async def clarify(self, understanding: Understanding) -> str:
        return self._clarification

    async def tie_break(self, candidates: list[Team], understanding: Understanding) -> Team:
        if self._tie_break_choice is not None and self._tie_break_choice in candidates:
            return self._tie_break_choice
        return candidates[0]  # deterministic fallback

    async def write_response(
        self,
        understanding: Understanding,
        enrichment: EnrichmentResult,
        decision: RoutingDecision,
    ) -> GeneratedOutput:
        if self._output is not None:
            return self._output
        return GeneratedOutput(
            customer_reply="Thanks for reaching out — we've logged your request and are on it.",
            internal_summary=(
                f"{len(understanding.issues)} issue(s); "
                f"routed to {decision.primary_owner.value}; "
                f"urgency {decision.effective_urgency.value}."
            ),
        )
