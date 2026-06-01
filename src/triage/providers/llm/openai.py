"""OpenAI implementation of the LLM seam (structured outputs; gpt-5.4-mini default).

Classification and prose use OpenAI's structured-outputs parsing, so results are
schema-valid by construction; the LLM stays confined to classify (understand),
ask (clarify), bounded pick (tie_break), and write (write_response). Live-verified
only when OPENAI_API_KEY is set (gated tests) — the heuristic provider is the
key-less default.
"""

from openai import AsyncOpenAI
from pydantic import BaseModel

from triage.conversations.models.enums import Team
from triage.conversations.models.schemas import (
    EnrichmentResult,
    GeneratedOutput,
    RoutingDecision,
    Understanding,
)
from triage.core.logging import get_logger

from .base import LLMProvider

_log = get_logger("llm")


def _log_usage(op: str, model: str, completion: object) -> None:
    """Emit token usage for cost observability (best-effort; usage may be absent)."""
    usage = getattr(completion, "usage", None)
    if usage is not None:
        _log.debug(
            "openai_usage",
            op=op,
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

_UNDERSTAND_SYSTEM = (
    "You are a support-triage classifier. Extract the distinct issues in the customer's "
    "message and assess it, using ONLY the provided enums. "
    "Urgency: low (no time pressure), normal (standard), high (blocking work / time-sensitive), "
    "critical (production down or severe, widely-impacting). "
    "Business impact: none, low, medium, high (revenue or many users affected), "
    "severe (revenue-blocking, data loss, or outage). "
    "Set escalation_signal true only if the customer explicitly asks to escalate / for a manager, "
    "or expresses acute urgency."
)
_CLARIFY_SYSTEM = (
    "You are a support agent. The message is too vague to route. Ask ONE concise clarifying "
    "message (you may request up to two closely-related missing details). Be brief and warm."
)
_GENERATE_SYSTEM = (
    "You are a support agent. Write a brief, warm customer-facing reply acknowledging ALL the "
    "issues and the routing/escalation, then a concise internal summary for the assigned team. "
    "Do not invent facts."
)


class _TeamChoice(BaseModel):
    team: Team


def _summary(u: Understanding) -> str:
    return (
        f"Issues: {[i.category.value for i in u.issues]}; sentiment {u.sentiment.value}; "
        f"urgency {u.urgency.value}; business impact {u.business_impact.value}."
    )


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def understand(
        self, message: str, prior: Understanding | None = None
    ) -> Understanding:
        messages: list[dict[str, str]] = [{"role": "system", "content": _UNDERSTAND_SYSTEM}]
        if prior is not None:
            # Give a terse running summary so a follow-up ("yes, it's urgent") is
            # classified in context. Deterministic merge still reconciles the result.
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Context from earlier in this conversation — {_summary(prior)} "
                        "The new message continues it; classify it as a continuation."
                    ),
                }
            )
        messages.append({"role": "user", "content": message})
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]  # SDK param typing is invariant on role
            response_format=Understanding,
        )
        _log_usage("understand", self._model, completion)
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed understanding")
        return parsed

    async def clarify(self, understanding: Understanding) -> str:
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _CLARIFY_SYSTEM},
                {"role": "user", "content": _summary(understanding)},
            ],
        )
        _log_usage("clarify", self._model, completion)
        return completion.choices[0].message.content or "Could you share a few more details?"

    async def tie_break(self, candidates: list[Team], understanding: Understanding) -> Team:
        options = [t.value for t in candidates]
        instruction = f"Pick the best owning team from EXACTLY these options: {options}."
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": _summary(understanding)},
            ],
            response_format=_TeamChoice,
        )
        _log_usage("tie_break", self._model, completion)
        parsed = completion.choices[0].message.parsed
        if parsed is not None and parsed.team in candidates:
            return parsed.team
        return candidates[0]

    async def write_response(
        self,
        understanding: Understanding,
        enrichment: EnrichmentResult,
        decision: RoutingDecision,
    ) -> GeneratedOutput:
        context = (
            f"Issues: {[i.category.value for i in understanding.issues]}. "
            f"Customer tier: {enrichment.tier.value}. "
            f"Routed to {decision.primary_owner.value}. "
            f"Escalations: {[e.value for e in decision.escalations]}. "
            f"Next action: {decision.next_action.value}."
        )
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _GENERATE_SYSTEM},
                {"role": "user", "content": context},
            ],
            response_format=GeneratedOutput,
        )
        _log_usage("write_response", self._model, completion)
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no generated output")
        return parsed
