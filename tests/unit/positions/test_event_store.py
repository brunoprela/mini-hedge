"""Unit tests for EventStoreRepository — serialize / deserialize (pure functions)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.positions.core.event_store import EventStoreRepository
from app.modules.positions.interfaces import (
    CorporateActionEventData,
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeSide,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PORT_ID = uuid4()
_TRADE_ID = uuid4()
_ACTION_ID = uuid4()
_NOW = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)


def _make_trade_event(
    side: TradeSide = TradeSide.BUY,
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("150.00"),
) -> TradeEvent:
    event_type = (
        PositionEventType.TRADE_BUY if side == TradeSide.BUY else PositionEventType.TRADE_SELL
    )
    return TradeEvent(
        event_type=event_type,
        timestamp=_NOW,
        data=TradeEventData(
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=side,
            quantity=quantity,
            price=price,
            trade_id=_TRADE_ID,
            currency="USD",
        ),
    )


def _make_corporate_action_event(
    event_type: PositionEventType = PositionEventType.STOCK_SPLIT,
    split_ratio: Decimal = Decimal("2"),
    dividend_amount: Decimal = Decimal("0"),
) -> TradeEvent:
    return TradeEvent(
        event_type=event_type,
        timestamp=_NOW,
        data=CorporateActionEventData(
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            currency="USD",
            action_id=_ACTION_ID,
            split_ratio=split_ratio,
            dividend_amount=dividend_amount,
        ),
    )


def _make_db_record(
    event_type: str,
    event_data: dict,
    created_at: datetime = _NOW,
) -> MagicMock:
    r = MagicMock()
    r.event_type = event_type
    r.event_data = event_data
    r.created_at = created_at
    return r


# ---------------------------------------------------------------------------
# Tests: serialize
# ---------------------------------------------------------------------------


class TestSerialize:
    def test_serialize_trade_buy(self) -> None:
        event = _make_trade_event(side=TradeSide.BUY)
        result = EventStoreRepository.serialize(event)

        assert result["portfolio_id"] == str(_PORT_ID)
        assert result["instrument_id"] == "AAPL"
        assert result["side"] == "buy"
        assert result["quantity"] == "100"
        assert result["price"] == "150.00"
        assert result["trade_id"] == str(_TRADE_ID)
        assert result["currency"] == "USD"

    def test_serialize_trade_sell(self) -> None:
        event = _make_trade_event(side=TradeSide.SELL)
        result = EventStoreRepository.serialize(event)

        assert result["side"] == "sell"

    def test_serialize_stock_split(self) -> None:
        event = _make_corporate_action_event(
            event_type=PositionEventType.STOCK_SPLIT,
            split_ratio=Decimal("3"),
        )
        result = EventStoreRepository.serialize(event)

        assert result["portfolio_id"] == str(_PORT_ID)
        assert result["instrument_id"] == "AAPL"
        assert result["action_id"] == str(_ACTION_ID)
        assert result["split_ratio"] == "3"
        assert result["dividend_amount"] == "0"
        assert result["currency"] == "USD"

    def test_serialize_dividend(self) -> None:
        event = _make_corporate_action_event(
            event_type=PositionEventType.DIVIDEND_PAID,
            dividend_amount=Decimal("500.00"),
        )
        result = EventStoreRepository.serialize(event)

        assert result["dividend_amount"] == "500.00"


# ---------------------------------------------------------------------------
# Tests: _deserialize
# ---------------------------------------------------------------------------


class TestDeserialize:
    def test_deserialize_trade_buy(self) -> None:
        record = _make_db_record(
            event_type="trade.buy",
            event_data={
                "portfolio_id": str(_PORT_ID),
                "instrument_id": "AAPL",
                "side": "buy",
                "quantity": "100",
                "price": "150.00",
                "trade_id": str(_TRADE_ID),
                "currency": "USD",
            },
        )
        event = EventStoreRepository._deserialize(record)

        assert event.event_type == PositionEventType.TRADE_BUY
        assert isinstance(event.data, TradeEventData)
        assert event.data.portfolio_id == _PORT_ID
        assert event.data.instrument_id == "AAPL"
        assert event.data.side == TradeSide.BUY
        assert event.data.quantity == Decimal("100")
        assert event.data.price == Decimal("150.00")
        assert event.data.trade_id == _TRADE_ID

    def test_deserialize_trade_sell(self) -> None:
        record = _make_db_record(
            event_type="trade.sell",
            event_data={
                "portfolio_id": str(_PORT_ID),
                "instrument_id": "MSFT",
                "side": "sell",
                "quantity": "50",
                "price": "300.00",
                "trade_id": str(_TRADE_ID),
                "currency": "EUR",
            },
        )
        event = EventStoreRepository._deserialize(record)

        assert event.event_type == PositionEventType.TRADE_SELL
        assert event.data.side == TradeSide.SELL
        assert event.data.currency == "EUR"

    def test_deserialize_stock_split(self) -> None:
        record = _make_db_record(
            event_type="stock.split",
            event_data={
                "portfolio_id": str(_PORT_ID),
                "instrument_id": "AAPL",
                "currency": "USD",
                "action_id": str(_ACTION_ID),
                "split_ratio": "2",
                "dividend_amount": "0",
            },
        )
        event = EventStoreRepository._deserialize(record)

        assert event.event_type == PositionEventType.STOCK_SPLIT
        assert isinstance(event.data, CorporateActionEventData)
        assert event.data.split_ratio == Decimal("2")
        assert event.data.action_id == _ACTION_ID

    def test_deserialize_dividend(self) -> None:
        record = _make_db_record(
            event_type="dividend.paid",
            event_data={
                "portfolio_id": str(_PORT_ID),
                "instrument_id": "AAPL",
                "currency": "USD",
                "action_id": str(_ACTION_ID),
                "split_ratio": "1",
                "dividend_amount": "500",
            },
        )
        event = EventStoreRepository._deserialize(record)

        assert event.event_type == PositionEventType.DIVIDEND_PAID
        assert isinstance(event.data, CorporateActionEventData)
        assert event.data.dividend_amount == Decimal("500")

    def test_deserialize_split_missing_action_id_defaults(self) -> None:
        """When action_id is missing, it should default to UUID(int=0)."""
        record = _make_db_record(
            event_type="stock.split",
            event_data={
                "portfolio_id": str(_PORT_ID),
                "instrument_id": "AAPL",
                "split_ratio": "3",
            },
        )
        event = EventStoreRepository._deserialize(record)

        assert event.data.action_id == UUID(int=0)
        assert event.data.currency == "USD"  # default

    def test_deserialize_preserves_timestamp(self) -> None:
        ts = datetime(2026, 1, 15, 9, 30, 0, tzinfo=UTC)
        record = _make_db_record(
            event_type="trade.buy",
            event_data={
                "portfolio_id": str(_PORT_ID),
                "instrument_id": "AAPL",
                "side": "buy",
                "quantity": "10",
                "price": "100",
                "trade_id": str(_TRADE_ID),
                "currency": "USD",
            },
            created_at=ts,
        )
        event = EventStoreRepository._deserialize(record)

        assert event.timestamp == ts


# ---------------------------------------------------------------------------
# Tests: roundtrip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_trade_roundtrip(self) -> None:
        """serialize -> _deserialize should return equivalent data."""
        original = _make_trade_event()
        serialized = EventStoreRepository.serialize(original)

        record = _make_db_record(
            event_type=original.event_type.value,
            event_data=serialized,
            created_at=original.timestamp,
        )
        restored = EventStoreRepository._deserialize(record)

        assert restored.event_type == original.event_type
        assert restored.data.portfolio_id == original.data.portfolio_id
        assert restored.data.quantity == original.data.quantity
        assert restored.data.price == original.data.price

    def test_corporate_action_roundtrip(self) -> None:
        original = _make_corporate_action_event(
            event_type=PositionEventType.DIVIDEND_PAID,
            dividend_amount=Decimal("250.50"),
        )
        serialized = EventStoreRepository.serialize(original)

        record = _make_db_record(
            event_type=original.event_type.value,
            event_data=serialized,
            created_at=original.timestamp,
        )
        restored = EventStoreRepository._deserialize(record)

        assert restored.event_type == original.event_type
        assert restored.data.dividend_amount == Decimal("250.50")
        assert restored.data.action_id == _ACTION_ID
