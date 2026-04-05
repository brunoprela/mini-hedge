"""Tests for ExecutionEngine — order lifecycle, fills, cancellation, rejection."""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from mock_exchange.execution.engine import ExecutionEngine, OrderStatus
from mock_exchange.shared.models import PriceQuote

if TYPE_CHECKING:
    from tests.conftest import FakeProducer

# ---------------------------------------------------------------------------
# Order submission (synchronous part)
# ---------------------------------------------------------------------------


class TestSubmitOrder:
    async def test_returns_acknowledged(self, execution_engine: ExecutionEngine) -> None:
        order = execution_engine.submit_order(
            client_order_id="cl-001",
            instrument_id="AAPL",
            side="buy",
            order_type="market",
            quantity=Decimal("100"),
        )
        assert order.status == OrderStatus.ACKNOWLEDGED

    async def test_stores_order(self, execution_engine: ExecutionEngine) -> None:
        order = execution_engine.submit_order(
            client_order_id="cl-001",
            instrument_id="AAPL",
            side="buy",
            order_type="market",
            quantity=Decimal("100"),
        )
        retrieved = execution_engine.get_order(order.exchange_order_id)
        assert retrieved is order

    async def test_unique_exchange_ids(self, execution_engine: ExecutionEngine) -> None:
        o1 = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        o2 = execution_engine.submit_order(
            "cl-002", "AAPL", "buy", "market", Decimal("100"),
        )
        assert o1.exchange_order_id != o2.exchange_order_id

    async def test_rejection(self, execution_engine: ExecutionEngine) -> None:
        execution_engine.update_config(reject_rate=1.0)
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        assert order.status == OrderStatus.REJECTED
        assert len(execution_engine._fill_tasks) == 0

    async def test_stores_limit_price(self, execution_engine: ExecutionEngine) -> None:
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "limit", Decimal("100"),
            limit_price=Decimal("150.00"),
        )
        assert order.limit_price == Decimal("150.00")


# ---------------------------------------------------------------------------
# Fill processing (async)
# ---------------------------------------------------------------------------


class TestFillProcessing:
    async def test_fill_completes_order(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        execution_engine.update_config(fill_delay_ms=0)
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == Decimal("100")

    async def test_fill_publishes_to_kafka(
        self,
        fake_producer: FakeProducer,
        execution_engine: ExecutionEngine,
    ) -> None:
        execution_engine.update_config(fill_delay_ms=0)
        execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        assert len(fake_producer.messages) == 1
        msg = fake_producer.messages[0]
        assert msg["topic"] == "shared.execution-reports"
        assert msg["event_type"] == "execution.report"

    async def test_fill_report_data_structure(
        self,
        fake_producer: FakeProducer,
        execution_engine: ExecutionEngine,
    ) -> None:
        execution_engine.update_config(fill_delay_ms=0)
        execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        data = fake_producer.messages[0]["data"]
        required_keys = {
            "exchange_order_id", "client_order_id", "instrument_id",
            "side", "status", "fill_id", "fill_quantity", "fill_price",
            "filled_at", "filled_quantity", "avg_fill_price",
        }
        assert required_keys.issubset(data.keys())

    async def test_partial_fill(
        self, fake_producer: FakeProducer,
    ) -> None:
        random.seed(42)
        engine = ExecutionEngine(producer=fake_producer, market_data=None)  # type: ignore[arg-type]
        engine.update_config(fill_delay_ms=0, partial_fill_rate=1.0)
        order = engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert Decimal("0") < order.filled_quantity < Decimal("100")

    async def test_slippage_within_bounds(
        self, fake_producer: FakeProducer,
    ) -> None:
        limit = Decimal("100.00")
        slippage_bps = 10.0
        max_slip = limit * Decimal(str(slippage_bps)) / Decimal("10000")

        for seed in range(50):
            random.seed(seed)
            engine = ExecutionEngine(
                producer=fake_producer, market_data=None,  # type: ignore[arg-type]
            )
            engine.update_config(fill_delay_ms=0, slippage_bps=slippage_bps)
            order = engine.submit_order(
                f"cl-{seed}", "AAPL", "buy", "limit", Decimal("100"),
                limit_price=limit,
            )
            await asyncio.sleep(0.05)
            fill_price = order.fills[0].price
            assert limit - max_slip <= fill_price <= limit + max_slip, (
                f"seed={seed}: fill_price={fill_price} outside bounds"
            )

    async def test_fill_uses_market_data_price(
        self, fake_producer: FakeProducer,
    ) -> None:
        mock_mds = MagicMock()
        mock_mds.get_latest_price.return_value = PriceQuote(
            instrument_id="AAPL",
            bid=Decimal("199.00"),
            ask=Decimal("201.00"),
            mid=Decimal("200.00"),
            volume=1000,
            timestamp="2024-01-01T00:00:00Z",
        )
        random.seed(0)
        engine = ExecutionEngine(
            producer=fake_producer, market_data=mock_mds,  # type: ignore[arg-type]
        )
        engine.update_config(fill_delay_ms=0, slippage_bps=0.0)
        order = engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        # With zero slippage, fill price should be exactly mid
        assert order.fills[0].price == Decimal("200.00")

    async def test_fill_defaults_to_100(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        random.seed(0)
        execution_engine.update_config(fill_delay_ms=0, slippage_bps=0.0)
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        assert order.fills[0].price == Decimal("100.00")


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


class TestCancelOrder:
    async def test_cancel_acknowledged(self, execution_engine: ExecutionEngine) -> None:
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        assert execution_engine.cancel_order(order.exchange_order_id) is True
        assert order.status == OrderStatus.CANCELLED

    async def test_cancel_filled_fails(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        execution_engine.update_config(fill_delay_ms=0)
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        await asyncio.sleep(0.05)
        assert execution_engine.cancel_order(order.exchange_order_id) is False

    async def test_cancel_rejected_fails(self, execution_engine: ExecutionEngine) -> None:
        execution_engine.update_config(reject_rate=1.0)
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        assert execution_engine.cancel_order(order.exchange_order_id) is False

    async def test_cancel_nonexistent_fails(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        assert execution_engine.cancel_order("nonexistent") is False

    async def test_cancel_already_cancelled_fails(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        order = execution_engine.submit_order(
            "cl-001", "AAPL", "buy", "market", Decimal("100"),
        )
        execution_engine.cancel_order(order.exchange_order_id)
        assert execution_engine.cancel_order(order.exchange_order_id) is False


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    async def test_update_config(self, execution_engine: ExecutionEngine) -> None:
        execution_engine.update_config(fill_delay_ms=500)
        assert execution_engine.config.fill_delay_ms == 500

    async def test_update_config_ignores_unknown(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        execution_engine.update_config(unknown_key=42)
        # Should not raise and config unchanged
        assert execution_engine.config.fill_delay_ms == 50

    async def test_get_order_nonexistent(
        self, execution_engine: ExecutionEngine,
    ) -> None:
        assert execution_engine.get_order("nonexistent") is None
