"""The language-model interface.

The LLM is confined to four bounded tasks — classify (``understand``), ask
(``clarify``), pick-from-a-set (``tie_break``), and write prose
(``write_response``). It never decides routing or escalation; that is the
rules engine's job. All methods are async to match real provider I/O.
"""

from abc import ABC, abstractmethod

from triage.conversations.models.enums import Team
from triage.conversations.models.schemas import (
    EnrichmentResult,
    GeneratedOutput,
    RoutingDecision,
    Understanding,
)


class LLMProvider(ABC):
    @abstractmethod
    async def understand(
        self, message: str, prior: Understanding | None = None
    ) -> Understanding:
        """Classify a message into structured, schema-validated signals."""

    @abstractmethod
    async def clarify(self, understanding: Understanding) -> str:
        """Generate one focused clarifying question for an under-specified message."""

    @abstractmethod
    async def tie_break(self, candidates: list[Team], understanding: Understanding) -> Team:
        """Pick one team from a provided candidate set (bounded selection only)."""

    @abstractmethod
    async def write_response(
        self,
        understanding: Understanding,
        enrichment: EnrichmentResult,
        decision: RoutingDecision,
    ) -> GeneratedOutput:
        """Write the customer reply and internal summary — prose only."""
