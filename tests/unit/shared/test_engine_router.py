"""Unit tests for EngineRouter and TenantSessionFactory engine routing."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.shared.database import EngineRouter


class TestEngineRouter:
    def test_default_engine_returned_when_no_customer(self) -> None:
        default = MagicMock()
        router = EngineRouter(default)
        assert router.resolve(None) is default

    def test_default_engine_returned_for_unknown_customer(self) -> None:
        default = MagicMock()
        router = EngineRouter(default)
        assert router.resolve("unknown-cust") is default

    def test_registered_customer_engine(self) -> None:
        default = MagicMock()
        cust_engine = MagicMock()
        router = EngineRouter(default)
        router.register("cust-1", cust_engine)
        assert router.resolve("cust-1") is cust_engine
        assert router.resolve("cust-2") is default

    def test_customer_count(self) -> None:
        default = MagicMock()
        router = EngineRouter(default)
        assert router.customer_count == 0
        router.register("cust-1", MagicMock())
        router.register("cust-2", MagicMock())
        assert router.customer_count == 2

    def test_default_engine_property(self) -> None:
        default = MagicMock()
        router = EngineRouter(default)
        assert router.default_engine is default

    def test_multiple_registrations_overwrite(self) -> None:
        default = MagicMock()
        engine_a = MagicMock()
        engine_b = MagicMock()
        router = EngineRouter(default)
        router.register("cust-1", engine_a)
        router.register("cust-1", engine_b)
        assert router.resolve("cust-1") is engine_b
        assert router.customer_count == 1
