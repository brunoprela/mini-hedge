"""Unit tests for PositionAggregate — pure logic, no database."""

from decimal import Decimal

from app.modules.positions.aggregate import PositionAggregate
from app.modules.positions.interface import PositionEventType, TradeSide
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trade_event


class TestBuy:
    def test_single_buy_updates_quantity_and_cost(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        event = make_trade_event(quantity="100", price="150.00")

        downstream = agg.apply(event)

        assert agg.quantity == Decimal("100")
        assert agg.cost_basis == Decimal("15000.00")
        assert agg.avg_cost == Decimal("150.00")
        assert len(agg.lots) == 1
        assert agg.lots[0].quantity == Decimal("100")
        assert len(downstream) == 1
        assert downstream[0]["event_type"] == PositionEventType.POSITION_CHANGED

    def test_multiple_buys_average_cost(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")

        agg.apply(make_trade_event(quantity="100", price="100.00"))
        agg.apply(make_trade_event(quantity="100", price="200.00"))

        assert agg.quantity == Decimal("200")
        assert agg.cost_basis == Decimal("30000.00")
        assert agg.avg_cost == Decimal("150.00")
        assert len(agg.lots) == 2


class TestSell:
    def test_sell_fifo_realized_pnl(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        agg.apply(make_trade_event(side=TradeSide.BUY, quantity="100", price="100.00"))
        agg.apply(make_trade_event(side=TradeSide.BUY, quantity="100", price="200.00"))

        downstream = agg.apply(
            make_trade_event(side=TradeSide.SELL, quantity="100", price="180.00")
        )

        # FIFO: sells from first lot (bought at 100), realized = 100 * (180 - 100) = 8000
        assert agg.quantity == Decimal("100")
        assert agg.realized_pnl == Decimal("8000.00")
        assert len(agg.lots) == 1
        assert agg.lots[0].price == Decimal("200.00")
        assert len(downstream) == 2  # position.changed + pnl.realized

    def test_sell_partial_lot(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        agg.apply(make_trade_event(side=TradeSide.BUY, quantity="100", price="100.00"))

        agg.apply(make_trade_event(side=TradeSide.SELL, quantity="50", price="120.00"))

        assert agg.quantity == Decimal("50")
        assert agg.realized_pnl == Decimal("1000.00")  # 50 * (120 - 100)
        assert len(agg.lots) == 1
        assert agg.lots[0].quantity == Decimal("50")

    def test_sell_all_clears_position(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        agg.apply(make_trade_event(side=TradeSide.BUY, quantity="100", price="100.00"))

        agg.apply(make_trade_event(side=TradeSide.SELL, quantity="100", price="110.00"))

        assert agg.quantity == Decimal("0")
        assert agg.cost_basis == Decimal("0")
        assert agg.realized_pnl == Decimal("1000.00")
        assert len(agg.lots) == 0


class TestShortSelling:
    def test_short_sell_creates_negative_lot(self) -> None:
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")

        agg.apply(make_trade_event(side=TradeSide.SELL, quantity="100", price="150.00"))

        assert agg.quantity == Decimal("-100")
        assert len(agg.lots) == 1
        assert agg.lots[0].quantity == Decimal("-100")

    def test_short_cost_basis_is_positive(self) -> None:
        """cost_basis should be absolute capital at risk, even for shorts."""
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        agg.apply(make_trade_event(side=TradeSide.SELL, quantity="100", price="150.00"))

        assert agg.cost_basis == Decimal("15000.00")  # abs(-100) * 150
        assert agg.avg_cost == Decimal("150.00")  # cost_basis / abs(quantity)

    def test_short_then_cover(self) -> None:
        """Short 100 @ $150, cover (buy back) 100 @ $140 → flat position.

        Note: the current aggregate creates a new long lot on buy rather
        than netting against the short lot. The net quantity is correct.
        """
        agg = PositionAggregate(portfolio_id=DEFAULT_PORTFOLIO_ID, instrument_id="AAPL")
        agg.apply(make_trade_event(side=TradeSide.SELL, quantity="100", price="150.00"))
        agg.apply(make_trade_event(side=TradeSide.BUY, quantity="100", price="140.00"))

        assert agg.quantity == Decimal("0")


class TestFromEvents:
    def test_rebuild_from_events(self) -> None:
        events = [
            make_trade_event(side=TradeSide.BUY, quantity="100", price="100.00"),
            make_trade_event(side=TradeSide.BUY, quantity="50", price="120.00"),
            make_trade_event(side=TradeSide.SELL, quantity="75", price="130.00"),
        ]

        agg = PositionAggregate.from_events(DEFAULT_PORTFOLIO_ID, "AAPL", events)

        assert agg.quantity == Decimal("75")
        # FIFO: sold 75 from first lot (100 at 100.00)
        # realized = 75 * (130 - 100) = 2250
        assert agg.realized_pnl == Decimal("2250.00")
        assert agg.version == 3
