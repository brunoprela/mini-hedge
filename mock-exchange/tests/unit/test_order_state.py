"""Tests for OrderState dataclass computed properties and OrderStatus enum."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from mock_exchange.execution.engine import Fill, OrderState, OrderStatus


class TestOrderStatus:
    def test_all_status_values_exist(self) -> None:
        assert OrderStatus.ACKNOWLEDGED == "acknowledged"
        assert OrderStatus.PARTIALLY_FILLED == "partially_filled"
        assert OrderStatus.FILLED == "filled"
        assert OrderStatus.REJECTED == "rejected"
        assert OrderStatus.CANCELLED == "cancelled"

    def test_status_count(self) -> None:
        assert len(OrderStatus) == 5


def _make_order(**kwargs: object) -> OrderState:
    defaults = {
        "exchange_order_id": "ex-001",
        "client_order_id": "cl-001",
        "instrument_id": "AAPL",
        "side": "buy",
        "order_type": "market",
        "quantity": Decimal("100"),
        "limit_price": None,
        "status": OrderStatus.ACKNOWLEDGED,
    }
    defaults.update(kwargs)
    return OrderState(**defaults)  # type: ignore[arg-type]


def _make_fill(qty: str, price: str) -> Fill:
    return Fill(
        fill_id="f-001",
        quantity=Decimal(qty),
        price=Decimal(price),
        filled_at=datetime.now(UTC),
    )


class TestFilledQuantity:
    def test_no_fills(self) -> None:
        order = _make_order()
        assert order.filled_quantity == Decimal("0")

    def test_single_fill(self) -> None:
        order = _make_order()
        order.fills.append(_make_fill("50", "150.00"))
        assert order.filled_quantity == Decimal("50")

    def test_multiple_fills(self) -> None:
        order = _make_order()
        order.fills.append(_make_fill("30", "150.00"))
        order.fills.append(_make_fill("70", "151.00"))
        assert order.filled_quantity == Decimal("100")


class TestAvgFillPrice:
    def test_no_fills_returns_none(self) -> None:
        order = _make_order()
        assert order.avg_fill_price is None

    def test_single_fill(self) -> None:
        order = _make_order()
        order.fills.append(_make_fill("100", "150.50"))
        assert order.avg_fill_price == Decimal("150.5000")

    def test_weighted_average(self) -> None:
        order = _make_order()
        order.fills.append(_make_fill("60", "100.00"))
        order.fills.append(_make_fill("40", "120.00"))
        # (6000 + 4800) / 100 = 108.0000
        assert order.avg_fill_price == Decimal("108.0000")
