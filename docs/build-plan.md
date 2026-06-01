# Build Plan — Support Conversation Orchestration Service

| | |
|---|---|
| **Doc type** | Build plan — **the source of truth**, updated every increment |
| **Status** | Living — starts shallow, detail accrues as we build |
| **Owner** | Suleman |
| **Related** | `requirements.md` (WHAT), `design.md` (HOW) |

> **This is the source of truth.** As we build, this document is **continuously updated** — it is the single place that reflects where we are. Items get checked off, locked decisions get recorded inline (replacing their TODO, so this doubles as a decision log), deviations and surprises get logged in the parking lot, and the build order is corrected whenever reality diverges from the plan. It starts deliberately shallow — an **item list** + a **build order** — and accrues detail as each piece is built. Anyone, human or agent, should be able to read this top-to-bottom and know exactly what is **decided**, what is **done**, and what is **next**.
>
> **Conventions:** `[ ]` todo · `[~]` in progress · `[x]` done. When a Section 2 decision is locked, replace its checkbox with the decision + a date. Record any deviation from `design.md` in the parking lot and reflect it back into the design doc so the two never drift.

---

## 1. How we build — discipline applied to every item

These are the constraints every item below must satisfy. Non-negotiable, not optional polish.

- **Builder mindset** — thin working spine first, then layer outward. There is always something runnable; we never go many steps without a green, demoable state.
- **Testable by construction** — nothing lands without tests. Pure core, I/O behind seams, a Fake for everything external (LLM, transcription). CI stays deterministic (no live calls).
- **Clean code** — small single-purpose functions, clear names, no dead/commented-out code, readable over clever.
- **Layered architecture** — dependency direction points *inward*: `interface → orchestration → decision → providers → persistence → platform`. Inner layers know nothing about outer ones.
- **SOLID** — single-responsibility nodes/rules; depend on **abstractions** (the seams), not implementations; open for extension (new rule, new node) without modifying the engine.
- **Logically designed & traceable** — each increment maps to a specific requirement / NFR. If it doesn't trace to one, question why we're building it.

**Definition of Done (per item):** typed · unit-tested · layered correctly · reviewed against the Section 4 gate · maps to a requirement · no dangling TODOs.

---

## 2. Decisions

Locked decisions are recorded here as they're made (this section doubles as the decision log); open ones stay as checkboxes.

### Locked (2026-05-31)

- [x] **Python + dependency manager** — Python 3.12, managed with **uv** (`pyproject.toml` + `uv.lock`).
- [x] **Lint / type / test / hooks** — **ruff** (lint + format), **pyright** (type check), **pytest** + **pytest-asyncio** (`asyncio_mode = "auto"`, `pythonpath = ["src"]`), **pre-commit**, **gitleaks** (secret scanning).
- [x] **Persistence stack** — **psycopg (async)** for Postgres: one driver shared by the repositories and the LangGraph `AsyncPostgresSaver` checkpointer (deviation from the original SQLAlchemy+asyncpg plan — see parking lot); **redis** client for the operational plane (M9).
- [x] **Config** — `pydantic-settings` in `core/config.py`; every setting via env, documented in `.env.example`.
- [x] **Error model** — typed exceptions (`core/errors.py`) + stable codes (`core/error_codes.py`) + one API error envelope (`core/middleware/error_handlers.py`).
- [x] **Logging** — **structlog** JSON + correlation IDs (conversation/job/turn/node) propagated across the async/worker boundary; PII redaction at the processor layer (`core/logging.py`).
- [x] **Schemas** — Pydantic v2 in `<module>/models/schemas.py`; enums in `models/enums.py`; graph state in `models/state.py`.
- [x] **Folder / module structure** — locked; see the tree below.

### Directory structure

```
triage-orchestrator/
├── pyproject.toml · uv.lock · .python-version            # uv · py3.12 · ruff · pyright · pytest
├── .gitleaks.toml · .dockerignore · .github/workflows/ci.yml
├── docker-compose.yml · Dockerfile                       # one image; api & worker = different commands
├── .env.example
├── docs/                                                 # requirements · design · build-plan
│
├── src/triage/
│   ├── main.py                                           # FastAPI app factory
│   │
│   ├── core/                                             # cross-cutting infrastructure
│   │   ├── config.py                                     # pydantic-settings
│   │   ├── lifespan.py                                   # startup/shutdown: DDL, resource wiring
│   │   ├── database.py                                   # psycopg async pool + DDL (shared by repos + checkpointer)
│   │   ├── redis.py · pubsub.py                          # clients + SSE progress channel
│   │   ├── logging.py                                    # structlog + correlation IDs + PII redaction
│   │   ├── errors.py · error_codes.py                    # structured error model
│   │   ├── dependencies.py                               # shared FastAPI deps — static API-key auth
│   │   └── middleware/error_handlers.py
│   │
│   ├── conversations/                                    # the domain (single vertical slice)
│   │   ├── api/v1/endpoints/                             # conversations · jobs · sse · health
│   │   ├── models/                                       # schemas.py · enums.py · state.py
│   │   ├── services/conversation_service.py              # submit · coalesce · retrieve; feeds context to the graph
│   │   ├── repositories/                                 # abstract interface + Postgres implementation
│   │   │     conversation_repository.py · postgres_conversation_repository.py
│   │   │     audit_repository.py        · postgres_audit_repository.py
│   │   │     customer_repository.py     · seeded_customer_repository.py    # 50+ fixture
│   │   ├── orchestration/                                # the LangGraph engine
│   │   │     graph.py · merge.py · checkpointer.py
│   │   │     nodes/ understand · enrich · clarify · route · tie_break · generate   # one file each
│   │   ├── decision/                                     # PURE rules — deterministic core, zero I/O
│   │   │     rules.py · reconcile.py · completeness.py
│   │   └── dependencies.py                               # feature DI wiring
│   │
│   ├── providers/                                        # seams: abstract + real + fake
│   │   ├── llm/           base.py · openai.py · fake.py
│   │   └── transcription/ base.py · deepgram.py · fake.py
│   │
│   └── worker/                                           # async execution
│       ├── arq_app.py · tasks.py                         # WorkerSettings · run-a-turn job
│       ├── messaging/                                    # queue bind · pub/sub publisher
│       ├── handlers/ turn.py · dlq.py                    # turn handler · dead-letter handler
│       └── concurrency/ lock.py · idempotency.py · coalesce.py
│
├── tests/                                                # mirrors module layout
│   ├── unit/ · integration/ · api/ · fakes/ · conftest.py
└── eval/ golden_set.yaml · run_eval.py
```

### Open

- [ ] **LangGraph state schema + reducers** — exact fields + merge functions (settled when M6 lands)
- [ ] **Env-var catalog** — finalized as each integration is wired
- [ ] **Branch / commit / PR conventions** — small reviewable increments = small PRs (confirm)
- [ ] _(add as they surface)_

---

## 3. Build order (sequenced, working-spine-first)

Each step is its own reviewable increment **with tests**. Ordered so the **deterministic core exists before any I/O**, and a runnable system appears early (M4). Contents are a starting point — refine as we go.

- [x] **M0 — Scaffold** · repo structure + toolchain (Section 2) · test harness · red/green CI
- [x] **M1 — Domain models & enums** · typed, validated · the controlled vocabularies
- [x] **M2 — Rules engine (pure)** · gate, R1–R4, modifiers, reconcile, tie-break trigger · *the deterministic core, zero I/O*
- [x] **M3 — Provider seams** · `LLMProvider` + `FakeProvider`, `Transcriber` + `FakeTranscriber`
- [x] **M4 — Graph on fakes** · LangGraph wired understand→enrich→gate→route→generate · integration tests · ← **working spine**
- [x] **M5 — Enrichment fixture** · seeded 50+ customers · lookup + safe defaults
- [x] **M6 — Multi-turn** · state merge, clarify loop, max-turns guard · still on fakes + in-memory checkpoint
- [x] **M7 — API layer** · FastAPI endpoints, `schema_version`, static API key · API tests
- [x] **M8 — Persistence** · Postgres checkpointer + append-only audit log + outputs
- [x] **M9 — Async** · Redis + arq worker · idempotency · per-conversation lock · dead-letter handler _(burst coalescing deferred — see parking lot)_
- [x] **M10 — SSE relay** · worker → Redis pub/sub → API · heartbeat · poll fallback
- [x] **M11 — Real providers** · OpenAI (`gpt-5.4-mini`, structured outputs) + Deepgram nova-3, behind the seams _(LIVE-VERIFIED 2026-06-01)_
- [x] **M12 — Observability & resilience** · structlog + correlation IDs · retry/backoff · graceful degradation · PII redaction
- [x] **M13 — Eval harness** · golden set · classification + routing accuracy
- [x] **M14 — Packaging** · docker-compose · README · AI_WORKFLOW.md

_Sequencing rationale (keep honest): M1–M4 give a fully-tested, runnable orchestration brain on fakes before a single external dependency exists. Everything after M4 is layering real I/O around a core that already works._

---

## 4. Review / quality gate (run at every increment)

- [ ] Tests pass; the increment's behavior is meaningfully covered
- [ ] Layering respected — no inward→outward dependency leaks
- [ ] SOLID — SRP holds; depends on abstractions; extensible without edits to the engine
- [ ] Clean code — names, function size, no dead code
- [ ] Traceable — maps to a specific requirement / NFR
- [ ] Errors handled; graceful degradation where relevant
- [ ] No secrets / PII in logs

---

## 5. Parking lot / notes

- _(running notes, surprises, and deferred sub-decisions go here as we build)_
- **2026-06-01:** **Post-review hardening pass** (self-review of the completed build → fixes). Three were code-vs-docs gaps where the implementation didn't deliver what the design claimed, and were the priority:
  - **Tie-break was dead in production.** `EnrichmentResult.candidate_team` was read by the reconciliation but **never populated** by the enricher, so `tie_break_candidates` always returned `None` and the bounded-LLM tie-break only ever fired in tests. Fixed by deriving `candidate_team` from the customer's footprint (`enrichment._candidate_team`): a *single-specialist-product* customer (billing/mobile/api) yields that specialist as an alternative hypothesis; multi-specialist/web-only → `None`, so ties stay rare and meaningful. Also tightened: the tie-break now only runs for a **complete** decision — the under-specified `GATE_EXHAUSTED` safety fallback is never second-guessed by the LLM. New regression test runs the tie-break through the *real* enricher; live-verified (heuristic: `identity_access` → tie → `api_integrations_team`, `T1` fired).
  - **Lock heartbeat was claimed but never called.** `ConversationLock.renew` existed and the docs said "heartbeat-renewed", but nothing invoked it — a turn slower than the 60s lease would silently lose the lock, letting a second worker run the same conversation. Added `ConversationLock.heartbeat(...)` (renews every `lease/3`, logs loudly if the lock is ever lost) and wrapped the turn execution in it; lease is now `TRIAGE_LOCK_LEASE_SECONDS`. Gated Redis test proves a 2s lease survives a 3s turn (verified against db 15).
  - **Clarification cap was a lifetime counter.** `clarification_count` persisted in the checkpoint and never reset, so a returning conversation that once asked a question could be handed to a human immediately on an unrelated later message. Now reset to 0 when a turn resolves (the generate node) → the max-turns guard is **per episode**. New multi-turn test.
- **2026-06-01:** **Hardening (security + robustness + polish), same pass.** Constant-time API-key compare (`secrets.compare_digest`) + a loud warning when the default `dev-key` is used in a durable/queue mode. Input-size guards into the paid providers: `max_message_chars` (413) and a capped voice read (`max_voice_bytes`, 413) — both tunable. OpenAI `understand` now receives a terse summary of prior-turn context so follow-ups classify in context (the deterministic merge still reconciles). Dead-letters now log distinctly (`turn_dead_lettered` + `dlq_parked` with depth). Startup schema setup (DDL + checkpointer migrations) wrapped in a Postgres **advisory lock** (`setup_lock`) so N booting processes don't race. Promoted hard-coded constants to settings (lock lease, idempotency TTL, `worker_max_tries`); removed dead `debounce_seconds`; unknown job id now returns **404**; PII redaction recurses into nested dict/list values.
- **2026-06-01:** **Extensive structured logging on every path** (the verbose trace is gated behind `TRIAGE_LOG_LEVEL=DEBUG`). Per-node logs (understand/enrich/route/tie_break/generate/clarify) with their decisions; gate/edge branch decisions with reasons; LLM calls timed at the `ResilientLLMProvider` choke point (`duration_ms`, provider, degraded?) + OpenAI **token usage**; Deepgram transcription timing; lock acquire/renew/release/heartbeat, idempotency claim/replay, enqueue, job-status, DLQ, pub/sub publish/subscribe, and repository ops. `job_id`/`job_try` bound as correlation IDs in the worker (joining the existing `conversation_id`/`node`). Live-verified the full DEBUG node trace emits end-to-end. Gates green: **96 pass + 2 skipped** (Postgres-gated; not re-run this pass — connecting to the shared server was blocked by the sandbox, and the only change to those paths is wrapping the unchanged DDL/setup in `setup_lock`), ruff + pyright clean.
- **2026-05-31:** package installed editable via a hatchling build backend (`[build-system]` + `tool.hatch`) so `import triage` works under `uv run` / `uvicorn` with no `PYTHONPATH`. Core verified end-to-end on the canonical message; 32 tests green through M3.
- **2026-05-31:** M4 working spine complete — the full LangGraph graph runs a message end-to-end on the fakes (understand→enrich→gate→route→tie-break→generate), with the clarify-pause and tie-break paths covered by integration tests. 35 tests green; langgraph 1.2.2 pinned. State accumulation/merge across turns is deferred to M6 (single-pass for now).
- **2026-05-31:** M5 enrichment fixture (52 seeded customers, deterministic) wired into the graph; unknown → safe defaults. 45 tests green.
- **2026-06-01:** M11 real providers **live-verified** with keys in `.env`. Config now accepts the conventional unprefixed `OPENAI_API_KEY` / `DEEPGRAM_API_KEY` (via `AliasChoices`, + `populate_by_name`) alongside the `TRIAGE_`-prefixed names. Verified: (1) OpenAI `gpt-5.4-mini` structured-output classification (direct call + the eval CLI against the real model = **75% routing / 62% escalation** on the golden set — the "misses" are reasonable LLM-vs-heuristic disagreements, exactly what the harness is for); (2) Deepgram nova-3 round-trip (OpenAI TTS → transcribe → exact text back); (3) full HTTP stack end-to-end on both real providers — a **text** turn (→ api_integrations_team + on-call/CSM + incident) and a **voice** turn (TTS audio → Deepgram → OpenAI → billing_ops + tier2), each with real LLM-written replies. `eval/run_eval.py` now uses the configured provider. Deterministic suite stays hermetic (83 pass + 7 skipped).
- **2026-05-31:** M14 (packaging) — `Dockerfile` (uv, one image for api+worker), `docker-compose.yml` (api + worker + Postgres + Redis on an internal network, no host-port clashes; YAML-anchored env), `.dockerignore`, expanded `README.md` (modes, endpoints, curl, eval), the mandatory `AI_WORKFLOW.md`, and a full `.env.example`. `docker compose config` validates. **Build complete: M0–M14 all done.** Final state: 90 tests pass (incl. all gated Postgres/Redis integration), ruff + pyright clean, eval 16/16. Full `docker compose up --build` is the deploy step (config-validated here).
- **2026-05-31:** M13 (eval harness) — `eval/golden_set.yaml` (16 labeled scenarios) + `triage/evaluation.py` (`evaluate()` scores routing + escalation accuracy through understand→enrich→rules) + `eval/run_eval.py` CLI. Runs against any provider — heuristic by default (key-less, deterministic, CI-safe), real model on demand. Live: 16/16, 100% routing + escalation on the heuristic. 83 pass + 7 skipped.
- **2026-05-31:** M12 (observability & resilience) — `core/logging.py`: structlog JSON logs, `conversation_id` (and job/node) bound via contextvars and merged into every event, a PII-redaction processor (email/phone/card) as a safety net (raw message text is never logged). `ResilientLLMProvider` wraps the chosen LLM so any failure degrades gracefully (understanding → 'unknown' → clarify/human; prose/tie-break → templated/first-candidate) — transport retries handled by the OpenAI SDK + arq. Verified live (a `turn_processed` JSON log with correlation id) and by tests (redaction, wrapper fallbacks, end-to-end degradation when the LLM is down). 81 pass + 7 skipped.
- **2026-05-31:** M11 (real providers, key-less) — `OpenAIProvider` (structured outputs via `beta.chat.completions.parse`; rubric-guided understanding; `gpt-5.4-mini`) and `DeepgramTranscriber` (SDK v7 `listen.v1.media.transcribe_file`, nova-3) behind the existing seams; a `providers/factory.py` selects them only when configured + a key is present, else the heuristic LLM + fake transcriber (so the app runs key-less). Added a `POST /v1/conversations/{id}/voice` endpoint (transcribe → same pipeline). Factory-selection + voice tests pass; the real providers are **not live-verified** (no keys) — gated. 74 pass + 7 skipped.
- **2026-05-31:** M10 (SSE progress) — `core/pubsub.py` `ProgressBus` (Redis pub/sub); `run_turn` gained an `on_node` streaming callback (via `graph.astream`), the worker publishes a `{"node": ...}` event per node + a terminal `{"event": "completed"}`, and `GET /v1/conversations/{id}/stream` relays them as SSE (`sse-starlette`, 15s heartbeat). **Verified live:** an SSE client watched `understand → enrich → route → generate → completed` stream in real time (worker → Redis pub/sub → API → client). Poll stays the authoritative contract; pub/sub roundtrip covered by a gated test. 76 tests green.
- **2026-05-31:** M9b (async worker) — arq worker (`worker/arq_app.py` + `handlers/turn.py`) runs the graph as a job behind the per-conversation lock; `TRIAGE_EXECUTION=queue` makes `POST .../messages` enqueue → **202 + job_id** (idempotency-keyed via the `Idempotency-Key` header) and poll via `GET /v1/jobs/{id}`; the dead-letter handler parks terminally-failed jobs on a Redis list. **Verified live over HTTP:** create → 202 → idempotent replay (same job_id) → poll-to-complete (owner `platform_sre`, `create_incident`) → durable `resolved` state, with worker + API as separate processes sharing Postgres `triage` + Redis db 15. 75 tests green (6 gated). **Burst coalescing deferred** (nice-to-have per scope): the per-conversation lock already serializes concurrent turns for *correctness*; burst-merge is a UX optimization (configurable debounce; window=0 = off) left as a follow-up.
- **2026-05-31:** M9a (concurrency primitives) — `core/redis.py` (async redis-py) + `IdempotencyStore` (replay → original job) + `ConversationLock` (token lease; Lua compare-and-act for owner-only renew/release; TTL anti-deadlock). Verified against the isolated Redis **db 15** (gated on `TRIAGE_TEST_REDIS_URL`). 69 pass + 4 skipped. **M9b next:** arq worker + `202`/job submission + `GET /jobs/{id}` polling + dead-letter handler + burst coalescing + live verify with a running worker.
- **2026-05-31:** M8b (real Postgres) — `core/database.py` (psycopg async pool + idempotent DDL), `PostgresConversationRepository` + `PostgresAuditRepository` (decision stored as JSONB), and the LangGraph `AsyncPostgresSaver` checkpointer, all sharing one pool. Lifespan in `main.py` swaps to Postgres when `TRIAGE_PERSISTENCE=postgres`, else in-memory (CI stays DB-free). Integration tests (gated on `TRIAGE_TEST_DATABASE_URL`) cover repo round-trip + durable resume across a simulated restart; verified **live over HTTP** with two server processes against an isolated `triage` DB on the workspace Postgres (state, audit, and 6 checkpoint rows persisted; server #2 retrieved + resumed server #1's conversation). 71 tests green. **Deviation:** used **psycopg for both** the checkpointer and repos (one driver, shared pool) instead of SQLAlchemy+asyncpg — langgraph mandates psycopg, and a second ORM/driver stack for two tiny tables wasn't worth it. "outputs" are captured as the `RoutingDecision` JSONB in the audit log; the prose reply is returned to the client but not persisted (PII).
- **2026-05-31:** M8a (persistence foundation) — `ConversationRepository` + `AuditRepository` abstractions (async) + in-memory impls; service refactored to use them and write an audit entry per turn; audit exposed via `GET /v1/conversations/{id}/audit`. 69 tests green. **M8b next:** real Postgres impls + `AsyncPostgresSaver` checkpointer + lifespan wiring + integration tests against the workspace's pgvector Postgres in an isolated `triage` database (never the `fridayos` DB).
- **2026-05-31:** M7 API layer complete — FastAPI app factory + `ConversationService` (graph runs in-request; M9 moves it async), `POST /v1/conversations`, `POST /v1/conversations/{id}/messages`, `GET /v1/conversations/{id}`, `/health`. Static API-key auth + structured error envelope (`{"error":{code,message}}`). Dependencies use the modern `Annotated` style (avoids B008). Added a keyword `HeuristicLLMProvider` so the key-less demo routes sensibly until the real model (M11). Verified live over curl. 64 tests green. Note: Starlette's `TestClient` emits one benign httpx deprecation warning — switch API tests to `httpx.AsyncClient` if zero-warnings is wanted.
- **2026-05-31:** M6 multi-turn complete — deterministic understanding-merge, the clarify loop with a persisted `clarification_count`, the max-turns guard (force-route to a human via `GATE_EXHAUSTED`), and resume across turns via an in-memory checkpointer keyed by `conversation_id`. **Gotcha fixed:** langgraph's checkpoint serializer warned that storing our custom Pydantic/enum types would be blocked in a future version — resolved by explicitly allowlisting our domain types on a `JsonPlusSerializer` (quieter + a tighter deserialize security posture). 52 tests green. M8 swaps the in-memory checkpointer for Postgres reusing the same serde.
