"""Unit tests for error cases and edge conditions."""

from decimal import Decimal

import pytest

from app.modules.positions.aggregate import PositionAggregate
from app.modules.positions.interface import TradeSide
from app.shared.events import BaseEvent, InProcessEventBus
from app.shared.request_context import RequestContext
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trade_event


class TestAggregateEdgeCases:
    def test_unknown_event_type_ignored(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        downstream = agg.apply(
            {"event_type": "unknown.type", "timestamp": "2026-01-01T00:00:00+00:00", "data": {}}
        )
        assert downstream == []
        assert agg.quantity == Decimal("0")
        assert agg.version == 0

    def test_zero_quantity_avg_cost(self) -> None:
        """avg_cost should be 0 when position is flat."""
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        assert agg.avg_cost == Decimal("0")

    def test_sell_more_than_owned_creates_short(self) -> None:
        """Selling more than owned should create a short position."""
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        agg.apply(make_trade_event(side=TradeSide.BUY, quantity="50", price="100.00"))
        agg.apply(make_trade_event(side=TradeSide.SELL, quantity="80", price="120.00"))

        # Sold 50 from lot (realized pnl = 50 * 20 = 1000), short 30 @ 120
        assert agg.quantity == Decimal("-30")
        assert agg.realized_pnl == Decimal("1000")
        assert len(agg.lots) == 1
        assert agg.lots[0].quantity == Decimal("-30")

    def test_from_events_empty_list(self) -> None:
        agg = PositionAggregate.from_events(DEFAULT_PORTFOLIO_ID, "AAPL", [])
        assert agg.quantity == Decimal("0")
        assert agg.version == 0


class TestRequestContextValidation:
    def test_empty_fund_slug_rejected(self) -> None:
        with pytest.raises(ValueError, match="fund_slug must not be empty"):
            RequestContext(
                actor_id="test",
                actor_type="user",
                fund_slug="",
            )

    def test_whitespace_fund_slug_rejected(self) -> None:
        with pytest.raises(ValueError, match="fund_slug must not be empty"):
            RequestContext(
                actor_id="test",
                actor_type="user",
                fund_slug="   ",
            )


class TestEventBusErrorPropagation:
    @pytest.mark.asyncio
    async def test_multiple_handler_failures(self) -> None:
        """All handlers run; all failures are surfaced."""
        bus = InProcessEventBus()

        async def bad1(event: BaseEvent) -> None:
            raise ValueError("bad1")

        async def bad2(event: BaseEvent) -> None:
            raise RuntimeError("bad2")

        bus.subscribe("t", bad1)
        bus.subscribe("t", bad2)

        with pytest.raises(ExceptionGroup) as exc_info:
            await bus.publish("t", BaseEvent(event_type="test", data={}))

        assert len(exc_info.value.exceptions) == 2
