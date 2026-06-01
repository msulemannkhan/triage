"""Async Redis client factory (redis-py).

Backs the operational plane: idempotency keys and per-conversation locks (and,
via arq, the job queue). The DB index lives in the URL, so an isolated logical
DB keeps these keys separate from anything else on the server.
"""

from redis.asyncio import Redis, from_url


def create_redis(url: str) -> Redis:
    return from_url(url, decode_responses=True)
