"""Dead-letter handler — a job that fails after all retries is parked on a Redis
list (never silently dropped) so a human can follow up."""

import json

from redis.asyncio import Redis

from triage.core.logging import get_logger

DLQ_KEY = "dlq"

_log = get_logger("worker")


async def dead_letter(redis: Redis, conversation_id: str, error: str) -> None:
    depth = await redis.rpush(  # type: ignore[misc]
        DLQ_KEY, json.dumps({"conversation_id": conversation_id, "error": error})
    )
    _log.error("dlq_parked", conversation_id=conversation_id, dlq_depth=depth, error=error)
