"""Redis pub/sub progress bus.

The worker publishes node-transition events as it runs a turn; the API's SSE
endpoint subscribes and relays them so a client can watch the graph advance.
Best-effort (no backlog) — poll (`GET /v1/jobs/{id}`) remains the authoritative
result contract, so a missed event is never a correctness problem.
"""

import json
from collections.abc import AsyncIterator

from redis.asyncio import Redis

from triage.core.logging import get_logger

_log = get_logger("pubsub")


def _channel(conversation_id: str) -> str:
    return f"progress:{conversation_id}"


class ProgressBus:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, conversation_id: str, event: dict) -> None:
        receivers = await self._redis.publish(_channel(conversation_id), json.dumps(event))
        _log.debug("progress_published", conversation_id=conversation_id, receivers=receivers)

    async def subscribe(self, conversation_id: str) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_channel(conversation_id))
        _log.debug("progress_subscribed", conversation_id=conversation_id)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(_channel(conversation_id))
            await pubsub.aclose()
            _log.debug("progress_unsubscribed", conversation_id=conversation_id)
