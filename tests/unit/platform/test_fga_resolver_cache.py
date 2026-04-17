"""Unit tests for FGAResolver cache-key normalization.

Verifies that ``customer_id=None`` and ``customer_id=""`` collapse to the
same cache entry, while distinct customer ids do not collide.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.modules.platform.services.auth.fga_client import (
    _NO_CUSTOMER,
    FGAResolver,
    _normalize_customer_id,
)


class TestNormalizeCustomerId:
    def test_none_maps_to_sentinel(self) -> None:
        assert _normalize_customer_id(None) == _NO_CUSTOMER

    def test_empty_string_maps_to_sentinel(self) -> None:
        assert _normalize_customer_id("") == _NO_CUSTOMER

    def test_real_id_passes_through(self) -> None:
        assert _normalize_customer_id("cust-1") == "cust-1"


def _make_resolver(relations: list[str] | None = None) -> FGAResolver:
    client = AsyncMock()
    client.list_relations = AsyncMock(return_value=relations or ["admin"])
    return FGAResolver(client)


class TestFGAResolverCacheKey:
    @pytest.mark.asyncio
    async def test_none_and_empty_customer_id_hit_same_cache_entry(self) -> None:
        resolver = _make_resolver(["admin"])

        # Prime with customer_id=None
        r1 = await resolver.resolve_fund_access("u-1", "fund-1", None)
        # Second call with "" should hit the cache, not re-query FGA
        r2 = await resolver.resolve_fund_access("u-1", "fund-1", "")

        assert r1 == r2
        resolver.client.list_relations.assert_called_once()
        # Only one entry in the cache, keyed by the sentinel
        assert len(resolver.cache) == 1
        assert ("u-1", "fund-1", _NO_CUSTOMER) in resolver.cache

    @pytest.mark.asyncio
    async def test_empty_then_none_also_hits_same_entry(self) -> None:
        resolver = _make_resolver(["admin"])

        await resolver.resolve_fund_access("u-1", "fund-1", "")
        await resolver.resolve_fund_access("u-1", "fund-1", None)

        resolver.client.list_relations.assert_called_once()
        assert len(resolver.cache) == 1

    @pytest.mark.asyncio
    async def test_different_customer_ids_do_not_collide(self) -> None:
        resolver = _make_resolver(["admin"])

        await resolver.resolve_fund_access("u-1", "fund-1", "cust-a")
        await resolver.resolve_fund_access("u-1", "fund-1", "cust-b")

        # Distinct customer ids -> two separate cache entries and two FGA calls
        assert resolver.client.list_relations.call_count == 2
        assert len(resolver.cache) == 2
        assert ("u-1", "fund-1", "cust-a") in resolver.cache
        assert ("u-1", "fund-1", "cust-b") in resolver.cache

    @pytest.mark.asyncio
    async def test_real_customer_does_not_collide_with_sentinel(self) -> None:
        resolver = _make_resolver(["admin"])

        await resolver.resolve_fund_access("u-1", "fund-1", None)
        await resolver.resolve_fund_access("u-1", "fund-1", "cust-a")

        assert resolver.client.list_relations.call_count == 2
        assert len(resolver.cache) == 2

    @pytest.mark.asyncio
    async def test_invalidate_clears_normalized_entries(self) -> None:
        resolver = _make_resolver(["admin"])

        await resolver.resolve_fund_access("u-1", "fund-1", None)
        await resolver.resolve_fund_access("u-1", "fund-1", "cust-a")
        assert len(resolver.cache) == 2

        resolver.invalidate("u-1", "fund-1")
        assert len(resolver.cache) == 0
