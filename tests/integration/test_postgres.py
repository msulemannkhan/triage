"""M8b: Postgres integration — repos round-trip + durable resume across a
simulated restart. Skipped unless TRIAGE_TEST_DATABASE_URL points at a reachable
Postgres (so CI stays DB-free)."""

import os
import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from triage.conversations.models.enums import (
    BusinessImpact,
    ConversationStatus,
    IssueCategory,
    NextAction,
    Sentiment,
    Team,
    Urgency,
)
from triage.conversations.models.schemas import AuditEntry, Issue, RoutingDecision, Understanding
from triage.conversations.orchestration.graph import build_graph, run_turn
from triage.conversations.repositories.postgres_audit_repository import PostgresAuditRepository
from triage.conversations.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)
from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.enrichment import make_enricher
from triage.core.database import create_pool, run_ddl, to_conninfo
from triage.providers.llm.fake import FakeLLMProvider

DB_URL = os.getenv("TRIAGE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="no TRIAGE_TEST_DATABASE_URL configured")

VAGUE = Understanding(
    issues=[Issue(category=IssueCategory.other)],
    sentiment=Sentiment.frustrated, urgency=Urgency.normal, business_impact=BusinessImpact.none,
)
CLEAR = Understanding(
    issues=[Issue(category=IssueCategory.api_integrations)],
    sentiment=Sentiment.frustrated, urgency=Urgency.high, business_impact=BusinessImpact.high,
)


async def _open_pool():
    pool = create_pool(to_conninfo(DB_URL))  # type: ignore[arg-type]
    await pool.open()
    await run_ddl(pool)
    return pool


async def test_postgres_repos_roundtrip():
    pool = await _open_pool()
    try:
        conversations = PostgresConversationRepository(pool)
        audit = PostgresAuditRepository(pool)
        cid = f"it-{uuid.uuid4().hex}"

        await conversations.add(cid, "cust_4821")
        assert await conversations.get_customer_id(cid) == "cust_4821"

        await audit.append(
            AuditEntry(
                conversation_id=cid,
                customer_id="cust_4821",
                status=ConversationStatus.resolved,
                decision=RoutingDecision(
                    primary_owner=Team.billing_ops,
                    next_action=NextAction.create_incident,
                    effective_urgency=Urgency.high,
                    effective_business_impact=BusinessImpact.high,
                    rules_fired=["R1", "R2"],
                ),
            )
        )
        log = await audit.list_for(cid)
        assert len(log) == 1
        assert log[0].decision is not None
        assert log[0].decision.primary_owner is Team.billing_ops
        assert log[0].decision.rules_fired == ["R1", "R2"]
    finally:
        await pool.close()


async def test_durable_resume_across_a_simulated_restart():
    pool = await _open_pool()
    try:
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        enrich = make_enricher(SeededCustomerRepository())
        cid = f"it-resume-{uuid.uuid4().hex}"

        # Turn 1 (vague) on one graph instance -> pauses for clarification.
        graph_a = build_graph(
            FakeLLMProvider(understanding=VAGUE, clarification="Which area?"),
            enrich,
            checkpointer=saver,
        )
        s1 = await run_turn(graph_a, conversation_id=cid, customer_id="cust_2290", message="broke")
        assert s1.status is ConversationStatus.awaiting_customer

        # Turn 2 on a FRESH graph + fresh saver (new "process"), same Postgres thread.
        # If state weren't durable, the merge would have no prior context.
        saver_b = AsyncPostgresSaver(pool)
        graph_b = build_graph(FakeLLMProvider(understanding=CLEAR), enrich, checkpointer=saver_b)
        s2 = await run_turn(
            graph_b, conversation_id=cid, customer_id="cust_2290", message="the API returns 500s"
        )
        assert s2.status is ConversationStatus.resolved
        assert s2.decision is not None
        assert s2.decision.primary_owner is Team.api_integrations_team
    finally:
        await pool.close()
