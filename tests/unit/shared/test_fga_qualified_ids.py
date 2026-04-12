"""Unit tests for customer-qualified FGA object IDs and per-request cache."""

from __future__ import annotations

from app.shared.fga.client import (
    clear_request_fga_cache,
    init_request_fga_cache,
    qualify_object_id,
    _request_fga_cache,
)


class TestQualifyObjectId:
    def test_with_customer_id(self) -> None:
        result = qualify_object_id("fund", "fund-123", "cust-abc")
        assert result == "fund:cust-abc/fund-123"

    def test_without_customer_id(self) -> None:
        result = qualify_object_id("fund", "fund-123", None)
        assert result == "fund:fund-123"

    def test_empty_customer_id(self) -> None:
        result = qualify_object_id("fund", "fund-123", "")
        assert result == "fund:fund-123"

    def test_platform_type_never_qualified(self) -> None:
        result = qualify_object_id("platform", "global", "cust-abc")
        assert result == "platform:global"

    def test_portfolio_with_customer(self) -> None:
        result = qualify_object_id("portfolio", "port-1", "cust-xyz")
        assert result == "portfolio:cust-xyz/port-1"

    def test_customer_type_with_customer(self) -> None:
        result = qualify_object_id("customer", "cust-1", "cust-parent")
        assert result == "customer:cust-parent/cust-1"


class TestRequestFGACache:
    def test_init_creates_empty_dict(self) -> None:
        init_request_fga_cache()
        cache = _request_fga_cache.get()
        assert cache is not None
        assert len(cache) == 0
        clear_request_fga_cache()

    def test_clear_resets_to_none(self) -> None:
        init_request_fga_cache()
        clear_request_fga_cache()
        assert _request_fga_cache.get() is None

    def test_cache_stores_values(self) -> None:
        init_request_fga_cache()
        cache = _request_fga_cache.get()
        assert cache is not None
        cache[("user:1", "can_view", "fund:abc")] = True
        assert cache[("user:1", "can_view", "fund:abc")] is True
        clear_request_fga_cache()

    def test_default_is_none(self) -> None:
        # Without init, cache should be None
        clear_request_fga_cache()
        assert _request_fga_cache.get() is None
