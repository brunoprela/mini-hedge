"""Async Redis client factory for pub/sub and caching."""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()


async def create_redis_client(redis_url: str, max_connections: int = 50) -> aioredis.Redis:
    """Create an async Redis client with connection pooling."""
    client: aioredis.Redis = aioredis.from_url(
        redis_url,
        decode_responses=True,
        max_connections=max_connections,
    )
    await client.ping()  # type: ignore[misc,unused-ignore]  # redis stubs type ping() as Awaitable[bool] | bool
    logger.info("redis_connected", url=redis_url, max_connections=max_connections)
    return client
