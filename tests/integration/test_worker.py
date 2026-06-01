"""M9b: the worker turn-job logic + dead-letter handler (gated on Redis).

Exercises the job function directly (no arq machinery) with an in-memory service
and a real Redis lock; the full arq flow is verified live over HTTP."""

import os
import uuid

import pytest

from triage.conversations.models.enums import (
    BusinessImpact,
    IssueCategory,
    Sentiment,
    Urgency,
)
from triage.conversations.models.schemas import Issue, Understanding
from triage.conversations.orchestration.graph import build_graph
from triage.conversations.repositories.seeded_customer_repository import SeededCustomerRepository
from triage.conversations.services.conversation_service import ConversationService
from triage.conversations.services.enrichment import make_enricher
from triage.core.redis import create_redis
from triage.providers.llm.fake import FakeLLMProvider
from triage.worker.concurrency.lock import ConversationLock
from triage.worker.handlers.dlq import DLQ_KEY, dead_letter
from triage.worker.handlers.turn import run_turn_job

REDIS_URL = os.getenv("TRIAGE_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="no TRIAGE_TEST_REDIS_URL configured")

BILLING = Understanding(
    issues=[Issue(category=IssueCategory.billing_payments)],
    sentiment=Sentiment.frustrated, urgency=Urgency.high, business_impact=BusinessImpact.high,
)


async def test_turn_job_runs_the_graph_and_returns_a_result():
    redis = create_redis(REDIS_URL)  # type: ignore[arg-type]
    try:
        graph = build_graph(
            FakeLLMProvider(understanding=BILLING), make_enricher(SeededCustomerRepository())
        )
        service = ConversationService.in_memory(graph)
        cid = await service.create("cust_4821")
        ctx = {
            "service": service,
            "lock": ConversationLock(redis),
            "redis_client": redis,
            "job_try": 1,
        }

        result = await run_turn_job(ctx, cid, "billing reports are down")

        assert result["status"] == "resolved"
        assert result["decision"]["routing"]["primary_owner"] == "billing_ops"
    finally:
        await redis.aclose()


async def test_dead_letter_parks_the_failed_job():
    redis = create_redis(REDIS_URL)  # type: ignore[arg-type]
    try:
        marker = f"conv-{uuid.uuid4().hex}"
        await dead_letter(redis, marker, "boom")
        items = await redis.lrange(DLQ_KEY, 0, -1)  # type: ignore[misc]
        assert any(marker in item for item in items)
        for item in items:  # cleanup our entry
            if marker in item:
                await redis.lrem(DLQ_KEY, 0, item)  # type: ignore[misc]
    finally:
        await redis.aclose()
