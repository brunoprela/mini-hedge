"""Factory functions for test data."""

from __future__ import annotations

from decimal import Decimal

from mock_exchange.market_data.simulator import InstrumentConfig


def make_small_universe() -> list[InstrumentConfig]:
    """3-instrument universe from different sectors for fast tests."""
    return [
        InstrumentConfig("TEST_TECH", 100.0, 0.10, 0.25, 10.0),
        InstrumentConfig("TEST_FIN", 200.0, 0.08, 0.20, 8.0),
        InstrumentConfig("TEST_NRG", 50.0, 0.06, 0.30, 12.0),
    ]


def make_order_params(**overrides: object) -> dict[str, object]:
    """Default order parameters for ExecutionEngine.submit_order()."""
    defaults: dict[str, object] = {
        "client_order_id": "test-001",
        "instrument_id": "AAPL",
        "side": "buy",
        "order_type": "market",
        "quantity": Decimal("100"),
    }
    defaults.update(overrides)
    return defaults


def make_submit_order_payload(**overrides: str) -> dict[str, str | None]:
    """JSON body for POST /api/v1/orders matching SubmitOrderRequest."""
    defaults: dict[str, str | None] = {
        "client_order_id": "test-001",
        "instrument_id": "AAPL",
        "side": "buy",
        "order_type": "market",
        "quantity": "100",
        "limit_price": None,
    }
    defaults.update(overrides)
    return defaults
