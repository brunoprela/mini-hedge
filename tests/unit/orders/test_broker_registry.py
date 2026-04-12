"""Unit tests for BrokerRegistry — multi-broker management."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.orders.core.broker_registry import BrokerRegistry


def _make_adapter(name: str = "sim") -> MagicMock:
    a = MagicMock()
    a.name = name
    return a


class TestRegisterAndGet:
    def test_register_and_get(self) -> None:
        reg = BrokerRegistry()
        adapter = _make_adapter("sim")
        reg.register("sim", adapter)

        assert reg.get("sim") is adapter

    def test_get_unknown_raises(self) -> None:
        reg = BrokerRegistry()

        with pytest.raises(KeyError, match="not registered"):
            reg.get("missing")

    def test_first_registered_becomes_default(self) -> None:
        reg = BrokerRegistry()
        a1 = _make_adapter("a")
        a2 = _make_adapter("b")
        reg.register("a", a1)
        reg.register("b", a2)

        assert reg.get_default() is a1
        assert reg.default_broker_id == "a"

    def test_explicit_default_overrides(self) -> None:
        reg = BrokerRegistry()
        a1 = _make_adapter("a")
        a2 = _make_adapter("b")
        reg.register("a", a1)
        reg.register("b", a2, default=True)

        assert reg.get_default() is a2
        assert reg.default_broker_id == "b"

    def test_get_default_no_brokers_raises(self) -> None:
        reg = BrokerRegistry()

        with pytest.raises(RuntimeError, match="No brokers registered"):
            reg.get_default()


class TestListAndProperties:
    def test_list_broker_ids(self) -> None:
        reg = BrokerRegistry()
        reg.register("sim", _make_adapter())
        reg.register("fix", _make_adapter())

        assert sorted(reg.list_broker_ids()) == ["fix", "sim"]

    def test_is_single_broker(self) -> None:
        reg = BrokerRegistry()
        assert reg.is_single_broker is True  # zero = single mode

        reg.register("sim", _make_adapter())
        assert reg.is_single_broker is True

        reg.register("fix", _make_adapter())
        assert reg.is_single_broker is False


class TestFillConsumer:
    def test_mark_and_check(self) -> None:
        reg = BrokerRegistry()

        assert reg.has_fill_consumer("sim") is False

        reg.mark_fill_consumer("sim")

        assert reg.has_fill_consumer("sim") is True
        assert reg.has_fill_consumer("other") is False
