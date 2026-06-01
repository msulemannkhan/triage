"""M10: ProgressBus publish/subscribe roundtrip against a real Redis (gated)."""

import asyncio
import os
import uuid

import pytest

from triage.core.pubsub import ProgressBus
from triage.core.redis import create_redis

REDIS_URL = os.getenv("TRIAGE_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="no TRIAGE_TEST_REDIS_URL configured")


async def test_subscriber_receives_published_progress_events():
    redis = create_redis(REDIS_URL)  # type: ignore[arg-type]
    try:
        bus = ProgressBus(redis)
        conversation_id = f"c-{uuid.uuid4().hex}"
        received: list[dict] = []

        async def consume() -> None:
            async for event in bus.subscribe(conversation_id):
                received.append(event)
                if event.get("event") == "completed":
                    break

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.2)  # let the subscription register (pub/sub has no backlog)
        await bus.publish(conversation_id, {"node": "understand"})
        await bus.publish(conversation_id, {"node": "route"})
        await bus.publish(conversation_id, {"event": "completed", "status": "resolved"})
        await asyncio.wait_for(task, timeout=5)

        assert {"node": "understand"} in received
        assert {"node": "route"} in received
        assert received[-1]["event"] == "completed"
    finally:
        await redis.aclose()
