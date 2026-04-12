"""Unit tests for PositionAggregate — event-sourced position domain logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.positions.core.aggregate import PositionAggregate
from app.modules.positions.interfaces import (
    CorporateActionEventData,
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeSide,
)

_PID = uuid4()
ZERO = Decimal(0)
_NOW = datetime.now(timezone.utc)
_seq = 0


def _next_ts() -> datetime:
    """Return a monotonically increasing timestamp so FIFO lot ordering is deterministic."""
    global _seq
    _seq += 1
    return _NOW + timedelta(seconds=_seq)


def _buy(qty: Decimal, price: Decimal, trade_id=None) -> TradeEvent:
    return TradeEvent(
        event_type=PositionEventType.TRADE_BUY,
        timestamp=_next_ts(),
        data=TradeEventData(
            portfolio_id=_PID,
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=qty,
            price=price,
            trade_id=trade_id or uuid4(),
            currency="USD",
        ),
    )


def _sell(qty: Decimal, price: Decimal, trade_id=None) -> TradeEvent:
    return TradeEvent(
        event_type=PositionEventType.TRADE_SELL,
        timestamp=_next_ts(),
        data=TradeEventData(
            portfolio_id=_PID,
            instrument_id="AAPL",
            side=TradeSide.SELL,
            quantity=qty,
            price=price,
            trade_id=trade_id or uuid4(),
            currency="USD",
        ),
    )


def _split(ratio: Decimal) -> TradeEvent:
    return TradeEvent(
        event_type=PositionEventType.STOCK_SPLIT,
        timestamp=_next_ts(),
        data=CorporateActionEventData(
            portfolio_id=_PID,
            instrument_id="AAPL",
            currency="USD",
            action_id=uuid4(),
            split_ratio=ratio,
        ),
    )


def _dividend(amount: Decimal) -> TradeEvent:
    return TradeEvent(
        event_type=PositionEventType.DIVIDEND_PAID,
        timestamp=_next_ts(),
        data=CorporateActionEventData(
            portfolio_id=_PID,
            instrument_id="AAPL",
            currency="USD",
            action_id=uuid4(),
            dividend_amount=amount,
        ),
    )


class TestBuy:
    def test_single_buy(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        events = agg.apply(_buy(Decimal("100"), Decimal("150")))

        assert agg.quantity == Decimal("100")
        assert agg.cost_basis == Decimal("15000")
        assert agg.avg_cost == Decimal("150")
        assert len(agg.lots) == 1
        assert len(events) == 1  # position_changed

    def test_multiple_buys(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        agg.apply(_buy(Decimal("100"), Decimal("100")))
        agg.apply(_buy(Decimal("100"), Decimal("200")))

        assert agg.quantity == Decimal("200")
        assert agg.cost_basis == Decimal("30000")
        assert agg.avg_cost == Decimal("150")
        assert len(agg.lots) == 2


class TestSell:
    def test_fifo_sell(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        agg.apply(_buy(Decimal("100"), Decimal("100")))
        agg.apply(_buy(Decimal("100"), Decimal("200")))

        events = agg.apply(_sell(Decimal("50"), Decimal("250")))

        assert agg.quantity == Decimal("150")
        # FIFO: sold from first lot at 100, realized 50 * (250-100) = 7500
        assert agg.realized_pnl == Decimal("7500")
        assert len(events) == 2  # position_changed + pnl_realized

    def test_sell_entire_position(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        agg.apply(_buy(Decimal("100"), Decimal("100")))
        agg.apply(_sell(Decimal("100"), Decimal("150")))

        assert agg.quantity == ZERO
        assert agg.realized_pnl == Decimal("5000")
        assert agg.lots == []

    def test_short_sell(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        agg.apply(_sell(Decimal("50"), Decimal("200")))

        assert agg.quantity == Decimal("-50")
        assert len(agg.lots) == 1
        assert agg.lots[0].quantity == Decimal("-50")


class TestSplit:
    def test_2_for_1_split(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        agg.apply(_buy(Decimal("100"), Decimal("200")))
        agg.apply(_split(Decimal("2")))

        assert agg.quantity == Decimal("200")
        assert agg.cost_basis == Decimal("20000")  # unchanged
        assert agg.avg_cost == Decimal("100")  # halved
        assert len(agg.lots) == 1
        assert agg.lots[0].quantity == Decimal("200")
        assert agg.lots[0].price == Decimal("100")


class TestDividend:
    def test_cash_dividend(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        agg.apply(_buy(Decimal("100"), Decimal("150")))
        events = agg.apply(_dividend(Decimal("300")))

        assert agg.realized_pnl == Decimal("300")
        assert len(events) == 2  # position_changed + pnl_realized


class TestAvgCost:
    def test_zero_quantity(self) -> None:
        agg = PositionAggregate(portfolio_id=_PID, instrument_id="AAPL")
        assert agg.avg_cost == ZERO


class TestFromEvents:
    def test_reconstructs_state(self) -> None:
        t0 = _NOW
        t1 = _NOW + timedelta(seconds=1)
        t2 = _NOW + timedelta(seconds=2)
        buy1 = TradeEvent(
            event_type=PositionEventType.TRADE_BUY,
            timestamp=t0,
            data=TradeEventData(
                portfolio_id=_PID, instrument_id="AAPL", side=TradeSide.BUY,
                quantity=Decimal("100"), price=Decimal("100"),
                trade_id=uuid4(), currency="USD",
            ),
        )
        buy2 = TradeEvent(
            event_type=PositionEventType.TRADE_BUY,
            timestamp=t1,
            data=TradeEventData(
                portfolio_id=_PID, instrument_id="AAPL", side=TradeSide.BUY,
                quantity=Decimal("50"), price=Decimal("120"),
                trade_id=uuid4(), currency="USD",
            ),
        )
        sell1 = TradeEvent(
            event_type=PositionEventType.TRADE_SELL,
            timestamp=t2,
            data=TradeEventData(
                portfolio_id=_PID, instrument_id="AAPL", side=TradeSide.SELL,
                quantity=Decimal("30"), price=Decimal("150"),
                trade_id=uuid4(), currency="USD",
            ),
        )
        agg = PositionAggregate.from_events(_PID, "AAPL", [buy1, buy2, sell1])

        assert agg.quantity == Decimal("120")
        assert agg.realized_pnl == Decimal("1500")  # FIFO: 30 * (150-100)
        assert agg.version == 3

    def test_mismatched_portfolio_raises(self) -> None:
        other_pid = uuid4()
        event = TradeEvent(
            event_type=PositionEventType.TRADE_BUY,
            timestamp=_NOW,
            data=TradeEventData(
                portfolio_id=other_pid,
                instrument_id="AAPL",
                side=TradeSide.BUY,
                quantity=Decimal("10"),
                price=Decimal("100"),
                trade_id=uuid4(),
                currency="USD",
            ),
        )

        with pytest.raises(ValueError, match="belongs to"):
            PositionAggregate.from_events(_PID, "AAPL", [event])

    def test_empty_events(self) -> None:
        agg = PositionAggregate.from_events(_PID, "AAPL", [])
        assert agg.quantity == ZERO
        assert agg.version == 0
