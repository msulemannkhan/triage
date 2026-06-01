"""Per-conversation lock — a Redis lease that serializes turns on the same
conversation. Held with a caller token so only the owner can renew (heartbeat)
or release it; the TTL guarantees a crashed worker can't deadlock the conversation.

A turn can outlive a single lease (several sequential LLM calls), so the owner
runs a ``heartbeat`` that renews the lease at one third of its duration while the
turn is in flight — without it, a slow turn would silently lose the lock and a
second worker could run the same conversation concurrently.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager, suppress
from typing import cast

from redis.asyncio import Redis

from triage.core.logging import get_logger

_PREFIX = "lock:"
_DEFAULT_LEASE = 60  # seconds

_log = get_logger("lock")

# Compare-and-act scripts so renew/release only affect a lock we still own.
_RENEW = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
)
_RELEASE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) else return 0 end"
)


class ConversationLock:
    def __init__(self, redis: Redis, lease_seconds: int = _DEFAULT_LEASE) -> None:
        self._redis = redis
        self._lease = lease_seconds

    def _key(self, conversation_id: str) -> str:
        return _PREFIX + conversation_id

    async def acquire(self, conversation_id: str, token: str) -> bool:
        acquired = bool(
            await self._redis.set(self._key(conversation_id), token, nx=True, ex=self._lease)
        )
        _log.debug(
            "lock_acquire",
            conversation_id=conversation_id,
            acquired=acquired,
            lease_seconds=self._lease,
        )
        return acquired

    async def renew(self, conversation_id: str, token: str) -> bool:
        result = await cast(
            Awaitable[int],
            self._redis.eval(_RENEW, 1, self._key(conversation_id), token, str(self._lease)),
        )
        return bool(result)

    async def release(self, conversation_id: str, token: str) -> bool:
        result = await cast(
            Awaitable[int],
            self._redis.eval(_RELEASE, 1, self._key(conversation_id), token),
        )
        released = bool(result)
        _log.debug("lock_release", conversation_id=conversation_id, released=released)
        return released

    @asynccontextmanager
    async def heartbeat(self, conversation_id: str, token: str) -> AsyncIterator[None]:
        """Keep an already-acquired lock alive for the duration of the block by
        renewing it every ``lease / 3`` seconds. If a renew ever fails (the lock
        was lost/expired), it logs loudly and stops — the caller's work continues,
        but the lost lock is now observable."""
        interval = max(self._lease / 3, 1.0)

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                renewed = await self.renew(conversation_id, token)
                if renewed:
                    _log.debug("lock_heartbeat", conversation_id=conversation_id)
                else:
                    _log.warning("lock_heartbeat_lost", conversation_id=conversation_id)
                    return

        task = asyncio.create_task(_loop())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
