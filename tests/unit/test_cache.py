"""Unit tests for the Redis caching layer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.shared.cache import (
    TTL_INSTRUMENT,
    TTL_PORTFOLIO,
    TTL_PRICE,
    CacheService,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def cache(mock_redis: AsyncMock) -> CacheService:
    return CacheService(mock_redis)


class TestCacheService:
    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self, cache: CacheService) -> None:
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_hit_returns_parsed_json(
        self, cache: CacheService, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = json.dumps({"ticker": "AAPL", "price": "150.00"})
        result = await cache.get("cache:price:AAPL")
        assert result == {"ticker": "AAPL", "price": "150.00"}

    @pytest.mark.asyncio
    async def test_set_serializes_with_ttl(
        self, cache: CacheService, mock_redis: AsyncMock
    ) -> None:
        await cache.set("key", {"a": 1}, ttl=60)
        mock_redis.set.assert_called_once_with("key", '{"a": 1}', ex=60)

    @pytest.mark.asyncio
    async def test_delete(self, cache: CacheService, mock_redis: AsyncMock) -> None:
        await cache.delete("key")
        mock_redis.delete.assert_called_once_with("key")


class TestDomainHelpers:
    @pytest.mark.asyncio
    async def test_instrument_cache(self, cache: CacheService, mock_redis: AsyncMock) -> None:
        data = {"ticker": "AAPL", "name": "Apple Inc"}
        await cache.set_instrument("inst-001", data)
        mock_redis.set.assert_called_once_with(
            "cache:instrument:inst-001",
            json.dumps(data),
            ex=TTL_INSTRUMENT,
        )

    @pytest.mark.asyncio
    async def test_price_cache_short_ttl(self, cache: CacheService, mock_redis: AsyncMock) -> None:
        await cache.set_price("inst-001", {"price": "150.00"})
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs[1]["ex"] == TTL_PRICE  # 5 seconds

    @pytest.mark.asyncio
    async def test_portfolio_summary(self, cache: CacheService, mock_redis: AsyncMock) -> None:
        await cache.set_portfolio_summary("port-001", {"nav": "100M"})
        call_kwargs = mock_redis.set.call_args
        assert call_kwargs[1]["ex"] == TTL_PORTFOLIO  # 30 seconds

    @pytest.mark.asyncio
    async def test_invalidate_portfolio(self, cache: CacheService, mock_redis: AsyncMock) -> None:
        await cache.invalidate_portfolio("port-001")
        mock_redis.delete.assert_called_once_with("cache:portfolio:port-001")
