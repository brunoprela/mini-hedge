"""Redis caching layer for frequently-read, slowly-changing data.

Provides a thin async wrapper around Redis for caching:
  - Security master instruments (TTL: 1 hour)
  - Latest price per instrument (TTL: 5 seconds)
  - Portfolio summary (TTL: 30 seconds)

Event-driven invalidation is handled by the caller — when a Kafka event
indicates stale data, the caller deletes the relevant cache key.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger()

# Cache key prefixes
_PREFIX_INSTRUMENT = "cache:instrument:"
_PREFIX_PRICE = "cache:price:"
_PREFIX_PORTFOLIO = "cache:portfolio:"

# TTL defaults (seconds)
TTL_INSTRUMENT = 3600  # 1 hour
TTL_PRICE = 5  # 5 seconds
TTL_PORTFOLIO = 30  # 30 seconds


class CacheService:
    """Async Redis cache for read-heavy data."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    # -----------------------------------------------------------------------
    # Generic get/set/delete
    # -----------------------------------------------------------------------

    async def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve a cached value, or ``None`` on miss."""
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        """Store a value with a TTL in seconds."""
        await self._redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        """Remove a cached value (explicit invalidation)."""
        await self._redis.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted."""
        keys = []
        async for key in self._redis.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    # -----------------------------------------------------------------------
    # Domain-specific helpers
    # -----------------------------------------------------------------------

    async def get_instrument(self, instrument_id: str) -> dict[str, Any] | None:
        return await self.get(f"{_PREFIX_INSTRUMENT}{instrument_id}")

    async def set_instrument(self, instrument_id: str, data: dict[str, Any]) -> None:
        await self.set(f"{_PREFIX_INSTRUMENT}{instrument_id}", data, TTL_INSTRUMENT)

    async def invalidate_instruments(self) -> int:
        return await self.delete_pattern(f"{_PREFIX_INSTRUMENT}*")

    async def get_price(self, instrument_id: str) -> dict[str, Any] | None:
        return await self.get(f"{_PREFIX_PRICE}{instrument_id}")

    async def set_price(self, instrument_id: str, data: dict[str, Any]) -> None:
        await self.set(f"{_PREFIX_PRICE}{instrument_id}", data, TTL_PRICE)

    async def get_portfolio_summary(self, portfolio_id: str) -> dict[str, Any] | None:
        return await self.get(f"{_PREFIX_PORTFOLIO}{portfolio_id}")

    async def set_portfolio_summary(self, portfolio_id: str, data: dict[str, Any]) -> None:
        await self.set(f"{_PREFIX_PORTFOLIO}{portfolio_id}", data, TTL_PORTFOLIO)

    async def invalidate_portfolio(self, portfolio_id: str) -> None:
        await self.delete(f"{_PREFIX_PORTFOLIO}{portfolio_id}")
