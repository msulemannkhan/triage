"""Idempotency keys — a retried submission with the same key returns the
original job rather than starting duplicate work.
"""

from redis.asyncio import Redis

from triage.core.logging import get_logger

_PREFIX = "idem:"
_DEFAULT_TTL = 24 * 60 * 60  # 24h

_log = get_logger("idempotency")


class IdempotencyStore:
    def __init__(self, redis: Redis, ttl_seconds: int = _DEFAULT_TTL) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def register(self, key: str, job_id: str) -> str:
        """Atomically claim ``key`` for ``job_id``. Returns the job that owns the
        key — the new one if this is the first time, or the original on a replay."""
        claimed = await self._redis.set(_PREFIX + key, job_id, nx=True, ex=self._ttl)
        if claimed:
            _log.debug("idempotency_claimed", key=key, job_id=job_id)
            return job_id
        existing = await self._redis.get(_PREFIX + key)
        _log.info("idempotency_replay", key=key, new_job_id=job_id, owning_job_id=existing)
        return existing if existing is not None else job_id
