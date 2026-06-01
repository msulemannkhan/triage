# AI_WORKFLOW.md

How this service was built with an AI-assisted workflow.

## AI Tools Used

- **Claude Code** (agentic CLI) — the primary tool, used end-to-end: to interrogate and pin the
  scope, author the specs, write all application code and tests, run the quality gates, and
  live-verify behavior against real Postgres/Redis.

The workflow was **spec-first, then milestone-by-milestone**:

1. **Adversarial scoping.** A structured "grill me" interview walked the decision tree one branch
   at a time (real LLM vs mock, orchestration paradigm, persistence, async model, etc.), each with
   a recommended answer. This produced three documents that are the source of truth:
   `docs/requirements.md` (what/who/why), `docs/design.md` (how), `docs/build-plan.md` (the
   sequenced plan + a running decision log).
2. **Build order = working spine first.** M0–M4 produced a fully-tested deterministic core (models
   → rules engine → provider seams → LangGraph graph on fakes) *before* any external dependency.
   Infrastructure (Postgres, Redis/arq, SSE, real providers) was layered on a core that already
   worked.
3. **Every milestone is a small, green increment** — written, gated (lint + types + tests), and
   for the I/O milestones live-verified over HTTP, then checkpointed in `build-plan.md`.
4. **Adversarial review of the finished build.** Once M0–M14 were green, the agent re-read the
   whole codebase against the specs looking for gaps the gates *can't* catch — and found three
   (a feature wired but never reachable, a guarantee the docs claimed but the code never enforced,
   a latent multi-turn bug). Each was fixed with a test, the docs were reconciled, and the pass is
   logged in `build-plan.md`. The lesson below ("How incorrect AI outputs were handled") leans on
   this: passing lint/types/tests is necessary, not sufficient.

## AI Development Workflow

- **AI-generated:** essentially all of it — the package layout, the rules engine, the LangGraph
  graph, the FastAPI layer, the Postgres/Redis integrations, the arq worker, the providers, the
  tests, and the docs.
- **Human-directed:** the decisions. Scope and architecture came from the interview answers
  (real LLM behind a seam, LangGraph, rules-first + bounded tie-break, Postgres+Redis, async via
  arq, SSE poll-authoritative). The human also made the deliberate **descopes** (rate limiting,
  burst coalescing) and **deviations** (psycopg for one driver instead of SQLAlchemy+asyncpg), and
  set the model (`gpt-5.4-mini`) and the "key-less by default" constraint.
- **How prompts evolved:** from broad, open scoping → precise per-milestone build prompts
  ("continue") → narrow, surgical fixes when a gate failed. Conventions (uv, ruff, pyright,
  repository pattern, `core/` package) were learned from a reference and **reimplemented from
  scratch** as original code.
- **How incorrect AI outputs were handled:** caught by the gates and live runs, then fixed. Real
  examples: discovering the actual OpenAI structured-output and Deepgram **v7 SDK** surfaces by
  introspecting the installed packages (not guessing); LangGraph's checkpoint serializer warning
  about custom types → fixed by explicitly allow-listing the domain types; psycopg async generics
  typing; an over-broad `pkill -f` that matched its own shell. Each was surfaced by ruff/pyright/
  pytest or a live run and resolved before the milestone was checked off.
- **The class of bug the gates miss — caught by adversarial review:** three issues passed *all*
  gates (green tests, zero lint, zero type errors) yet were still wrong, because each was a
  mismatch between intent and behavior, not a syntactic/type error:
  (1) the **bounded LLM tie-break was dead code in production** — its trigger field was read but
  never populated, so it only ever fired in tests that hand-built it; (2) the per-conversation lock
  was documented as **"heartbeat-renewed" but nothing called `renew()`**, so a slow turn could
  silently lose the lock; (3) the clarification budget was a **lifetime counter that never reset**,
  so a returning conversation could be handed to a human on an unrelated later message. The fix for
  each shipped with a regression test that now *locks the behavior the gates couldn't assert* (e.g.
  "the tie-break fires through the real enricher", "a 2s lease survives a 3s turn"), and the docs
  were corrected so the spec and code agree again. Takeaway: the gates verify the code does what it
  says; only a review against the spec verifies the code does what it **should**.

## Validation & Reliability

- **How AI code was validated:** a hard gate per milestone — `pytest` (all green), `ruff` (zero
  lint), `pyright` (zero type errors). Nothing was marked done until green.
- **Testing approach:** a pyramid that is deterministic and CI-safe — unit tests for the rules
  engine / completeness gate / state-merge / lock / idempotency; integration tests that run the
  full graph on a **scripted fake provider** (no live calls); API tests via the test client;
  **gated** integration tests that run against real Postgres/Redis only when configured (they skip
  cleanly otherwise); and a **golden-set eval harness** for routing/escalation accuracy. The async,
  durable, and SSE paths were additionally verified **live over HTTP** (including durability across
  a simulated restart).
- **Orchestration reliability / reducing LLM drift:** deterministic control flow — conditional
  edges and the routing decision are plain Python; the LLM is boxed into classification and prose
  via **structured outputs** over fixed enums. It never picks a route. Same input → same decision.
- **Hallucination / routing mitigation:** rules-first engine + a *bounded* LLM tie-break (chooses
  only from a provided candidate set, with a deterministic fallback) + controlled vocabularies.
- **Retry / fallback handling:** transport retries from the OpenAI SDK and arq; a **dead-letter
  handler** for jobs that fail after retries; and a `ResilientLLMProvider` that degrades any LLM
  failure gracefully (understanding → 'unknown' → clarification/human; prose/tie-break →
  templated/first-candidate) so a turn never crashes.
- **Edge cases covered:** vague message → clarify loop with a **max-turns guard** → human handoff;
  unknown customer → safe defaults; duplicate submission → idempotency replay; concurrent turns →
  per-conversation lock; LLM down → graceful degradation; multi-issue message → reconcile to one
  primary owner.

## Production Engineering Thinking

- **Scaling:** stateless API + N horizontally-scalable arq workers behind shared Postgres + Redis;
  no in-process state required for correctness.
- **Async / retry:** arq job queue, `202 + job_id` submit, poll + SSE retrieve; queue-level retries
  + DLQ.
- **Observability:** structlog JSON logs with correlation IDs (`conversation_id`/`job_id`/`job_try`/
  `node`) merged into every event, on **every path** — each graph node and its decision, the
  deterministic gate/edge branches with their reason, LLM calls timed at the `ResilientLLMProvider`
  choke point (`duration_ms`, provider, degraded?) plus OpenAI **token usage**, transcription
  timing, and the operational plane (lock acquire/renew/heartbeat/release, idempotency claim/replay,
  enqueue, job status, dead-letter, pub/sub, repositories). The verbose per-node trace is gated
  behind `TRIAGE_LOG_LEVEL=DEBUG` so production stays at INFO. An append-only **audit log** records
  every decision and its rationale (`rules_fired`); SSE exposes live progress; PII is redacted
  recursively (incl. nested values). Prometheus `/metrics` + OpenTelemetry tracing are the next step.
- **Concurrency / idempotency:** a Redis lease lock (token-based, heartbeat-renewed, TTL
  anti-deadlock) serializes turns per conversation; idempotency keys make retried submissions safe.
- **Orchestration monitoring:** the audit log + correlation-tagged logs make any decision fully
  reconstructable.
- **Deployment:** `docker compose` (api + worker + postgres + redis), one image for api/worker.
  CI/CD, k8s, and a secrets manager are the documented production next steps.
- **Security/PII:** secrets via env only; a static API key guards endpoints; logs redact
  email/phone/card patterns and never carry raw message bodies.

## Team Workflow

- **Organizing an AI-first team:** specs as the source of truth (the three docs), small reviewable
  increments, and the quality gates as the contract. The build-plan doubles as a **living decision
  log** — locked decisions, deviations, and deferrals are all recorded with rationale.
- **Code review:** the automated gates (lint + types + tests) are the first reviewer; a per-increment
  checklist (layering respected, SOLID, traceable to a requirement, no PII in logs) is the second;
  the adversarial spec interview is review applied *before* code exists; and an **adversarial review
  of the finished build** — re-reading the whole codebase against the specs — is review applied
  *after*, which is what caught the three "passes-the-gates-but-wrong" bugs above.
- **Quality gates:** green `pytest` / `ruff` / `pyright`, traceability to a requirement, and a clean
  separation of the deterministic core from I/O (so the core is testable without infrastructure).
- **Risks of AI-generated code & mitigations:** *plausible-but-wrong* output → caught by gates +
  live verification; *SDK/API drift* → introspect the actually-installed library surface rather than
  trusting memory; *silent scope creep* → every descope/deviation is an explicit, logged decision;
  *unverifiable code* (e.g. providers needing keys) → wired behind seams, gated, and clearly marked
  not-live-verified rather than pretended-done.
- **Governance:** deviations and descopes live in the build-plan parking lot; reference patterns are
  learned but reimplemented as original code, never copied.
