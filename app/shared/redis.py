"""Async Redis client factory for pub/sub and caching."""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()


async def create_redis_client(redis_url: str) -> aioredis.Redis:
    """Create an async Redis client with connection pooling."""
    client: aioredis.Redis = aioredis.from_url(
        redis_url,
        decode_responses=True,
        max_connections=20,
    )
    await client.ping()
    logger.info("redis_connected", url=redis_url)
    return client
