"""Extended unit tests for PositionService — execute_trade, get_position_at with events."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.positions.interfaces import (
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeRequest,
    TradeSide,
)
from app.modules.positions.services.position import PositionService

_PORT_ID = uuid4()
_TRADE_ID = uuid4()
_NOW = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)


def _make_position_record(
    instrument_id: str = "AAPL",
    quantity: Decimal = Decimal("100"),
) -> MagicMock:
    r = MagicMock()
    r.portfolio_id = str(_PORT_ID)
    r.instrument_id = instrument_id
    r.quantity = quantity
    r.avg_cost = Decimal("150")
    r.cost_basis = quantity * Decimal("150")
    r.market_price = Decimal("155")
    r.market_value = quantity * Decimal("155")
    r.unrealized_pnl = quantity * Decimal("5")
    r.currency = "USD"
    r.last_updated = _NOW
    return r


def _make_service(
    *,
    position_record: MagicMock | None = None,
    event_store_events: list | None = None,
) -> PositionService:
    position_repo = AsyncMock()
    position_repo.get_position = AsyncMock(return_value=position_record)
    position_repo.get_by_portfolio = AsyncMock(return_value=[])
    position_repo.get_portfolio_summary = AsyncMock(return_value=None)

    lot_repo = AsyncMock()
    lot_repo.get_lots = AsyncMock(return_value=[])

    trade_handler = AsyncMock()
    trade_handler.handle_trade = AsyncMock()

    event_store = None
    if event_store_events is not None:
        event_store = AsyncMock()
        event_store.get_by_aggregate = AsyncMock(return_value=event_store_events)

    return PositionService(
        position_repo=position_repo,
        lot_repo=lot_repo,
        trade_handler=trade_handler,
        event_store=event_store,
    )


class TestExecuteTrade:
    async def test_executes_and_returns_position(self) -> None:
        record = _make_position_record("AAPL")
        svc = _make_service(position_record=record)

        request = TradeRequest(
            portfolio_id=_PORT_ID,
            instrument_id="aapl",  # lowercase — service should uppercase
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
        )
        ctx = MagicMock()
        ctx.fund_slug = "alpha"

        result = await svc.execute_trade(request, ctx)

        assert result.instrument_id == "AAPL"
        assert result.portfolio_id == _PORT_ID
        svc._trade_handler.handle_trade.assert_called_once()
        # Verify instrument_id was uppercased
        call_kwargs = svc._trade_handler.handle_trade.call_args.kwargs
        assert call_kwargs["instrument_id"] == "AAPL"

    async def test_raises_lookup_error_when_readback_fails(self) -> None:
        svc = _make_service(position_record=None)

        request = TradeRequest(
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
        )
        ctx = MagicMock()

        with pytest.raises(LookupError, match="Position read-back failed"):
            await svc.execute_trade(request, ctx)

    async def test_passes_idempotency_key(self) -> None:
        record = _make_position_record("AAPL")
        svc = _make_service(position_record=record)

        request = TradeRequest(
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
            idempotency_key="my-key-123",
        )
        ctx = MagicMock()

        await svc.execute_trade(request, ctx)

        call_kwargs = svc._trade_handler.handle_trade.call_args.kwargs
        assert call_kwargs["idempotency_key"] == "my-key-123"


class TestGetPositionAtWithEvents:
    async def test_returns_position_from_replayed_events(self) -> None:
        """When events exist before the timestamp, returns reconstructed position."""
        buy_event = TradeEvent(
            event_type=PositionEventType.TRADE_BUY,
            timestamp=_NOW,
            data=TradeEventData(
                portfolio_id=_PORT_ID,
                instrument_id="AAPL",
                side=TradeSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("150"),
                trade_id=_TRADE_ID,
                currency="USD",
            ),
        )
        svc = _make_service(event_store_events=[buy_event])

        result = await svc.get_position_at(_PORT_ID, "AAPL", _NOW)

        assert result is not None
        assert result.quantity == Decimal("100")
        assert result.avg_cost == Decimal("150")
        assert result.instrument_id == "AAPL"
        assert result.portfolio_id == _PORT_ID
        # market data fields are zero for event replay
        assert result.market_price == Decimal("0")
        assert result.market_value == Decimal("0")
        assert result.last_updated == _NOW
