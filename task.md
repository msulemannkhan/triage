# Triage Orchestrator — Requirements

A conversational orchestration service for a contact-center/support environment. It takes an
inbound customer message, processes it through a structured, controlled pipeline, and emits a
deterministic decision packet for downstream routing and response.

Example input:
*"I contacted support twice already. My mobile app crashes after login, billing reports are
unavailable, and I need urgent assistance."*

## Functional Requirements

### 1. Request Understanding

Decompose an inbound message into structured signals:

- Issue category (supports multiple distinct issues per message)
- Customer sentiment
- Urgency
- Whether escalation is requested
- Business impact level

Text is the primary input; voice input is transcribed and then follows the identical pipeline.

### 2. Context Enrichment

Attach customer context to the request:

- Customer tier
- Previous interaction history
- Related product/service
- Affected system/component
- Suggested internal team

This context is retrieved from a customer store (mocked/seeded is acceptable). Unknown customers
degrade to safe defaults rather than failing.

### 3. Controlled Orchestration

A multi-step orchestration flow — **not a single prompt** — that:

- Routes requests dynamically and decides which action executes next
- Maintains a structured conversational flow across turns
- Adapts to urgency and context (e.g. escalates, or asks for clarification when under-specified)
- Generates operational recommendations

Orchestration must be **reliable and deterministic**: control flow and every routing/escalation
decision are made by explicit rules, not by the model. The LLM is confined to classification
(schema-bound, fixed vocabularies) and prose generation, so the same input yields the same
decision. LLM drift is mitigated by rules-first decisioning, a bounded tie-break that may only
choose from a provided candidate set, and graceful degradation when the model is unavailable.

### 4. Output Generation

Produce a structured decision packet containing:

- Customer-facing response
- Internal support summary
- Routing decision
- Escalation recommendation
- Suggested operational next action

Every decision is logged to an append-only audit trail with the rationale (which rules fired).

## Technical Requirements

- Python + FastAPI.
- Clear orchestration structure, readable code, clean layered architecture.
- README with setup instructions.
- Async request handling, structured logging, and basic monitoring hooks (audit log + progress
  stream).
- Containerized for local and deployed runs (Docker).
- An evaluation harness for routing/escalation accuracy.
