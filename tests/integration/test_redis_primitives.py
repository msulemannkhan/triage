"""M9a: idempotency + per-conversation lock against a real Redis.

Skipped unless TRIAGE_TEST_REDIS_URL points at a reachable Redis (isolated DB
index), so CI stays infra-free."""

import asyncio
import os
import uuid

import pytest

from triage.core.redis import create_redis
from triage.worker.concurrency.idempotency import IdempotencyStore
from triage.worker.concurrency.lock import ConversationLock

REDIS_URL = os.getenv("TRIAGE_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="no TRIAGE_TEST_REDIS_URL configured")


async def test_idempotency_replay_returns_the_original_job():
    redis = create_redis(REDIS_URL)  # type: ignore[arg-type]
    try:
        store = IdempotencyStore(redis, ttl_seconds=60)
        key = f"k-{uuid.uuid4().hex}"
        assert await store.register(key, "job-a") == "job-a"
        assert await store.register(key, "job-b") == "job-a"  # replay -> original
        assert await store.register(f"k-{uuid.uuid4().hex}", "job-c") == "job-c"
    finally:
        await redis.aclose()


async def test_conversation_lock_is_exclusive_renewable_and_safe():
    redis = create_redis(REDIS_URL)  # type: ignore[arg-type]
    try:
        lock = ConversationLock(redis, lease_seconds=30)
        cid = f"c-{uuid.uuid4().hex}"

        assert await lock.acquire(cid, "tok1") is True
        assert await lock.acquire(cid, "tok2") is False        # already held
        assert await lock.renew(cid, "tok1") is True            # owner can renew
        assert await lock.renew(cid, "intruder") is False       # non-owner cannot
        assert await lock.release(cid, "intruder") is False     # non-owner cannot release
        assert await lock.release(cid, "tok1") is True          # owner releases
        assert await lock.acquire(cid, "tok2") is True          # now free
        await lock.release(cid, "tok2")
    finally:
        await redis.aclose()


async def test_heartbeat_keeps_a_short_lease_alive_past_its_ttl():
    # Without the heartbeat, a 2s lease would expire mid-turn and a second worker
    # could grab the lock. The heartbeat (renews at lease/3) must keep it held.
    redis = create_redis(REDIS_URL)  # type: ignore[arg-type]
    try:
        lock = ConversationLock(redis, lease_seconds=2)
        cid = f"c-{uuid.uuid4().hex}"
        assert await lock.acquire(cid, "owner") is True
        async with lock.heartbeat(cid, "owner"):
            await asyncio.sleep(3)  # outlive the raw 2s lease
            assert await lock.acquire(cid, "intruder") is False  # still held, renewed
        assert await lock.release(cid, "owner") is True
    finally:
        await redis.aclose()
