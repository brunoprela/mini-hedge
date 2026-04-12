"""Unit tests for PositionProjector — project, _project_lots, rebuild."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.positions.core.position_projector import PositionProjector
from app.modules.positions.interfaces import (
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeSide,
)

_PORT_ID = uuid4()
_TRADE_ID = uuid4()
_NOW = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)


def _make_aggregate(
    quantity: Decimal = Decimal("100"),
    avg_cost: Decimal = Decimal("150"),
    cost_basis: Decimal = Decimal("15000"),
    realized_pnl: Decimal = Decimal("0"),
    lots: list | None = None,
) -> MagicMock:
    agg = MagicMock()
    agg.portfolio_id = _PORT_ID
    agg.instrument_id = "AAPL"
    agg.quantity = quantity
    agg.avg_cost = avg_cost
    agg.cost_basis = cost_basis
    agg.realized_pnl = realized_pnl
    agg.lots = lots or []
    return agg


def _make_lot(
    lot_id=None,
    quantity: Decimal = Decimal("50"),
    original_quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("150"),
    acquired_at: datetime = _NOW,
    trade_id=None,
) -> MagicMock:
    lot = MagicMock()
    lot.lot_id = lot_id or uuid4()
    lot.quantity = quantity
    lot.original_quantity = original_quantity
    lot.price = price
    lot.acquired_at = acquired_at
    lot.trade_id = trade_id or _TRADE_ID
    return lot


class TestProject:
    async def test_upserts_position_and_projects_lots(self) -> None:
        repo = AsyncMock()
        projector = PositionProjector(repo)
        session = AsyncMock()
        agg = _make_aggregate()

        await projector.project(agg, session=session, currency="USD")

        repo.upsert.assert_called_once_with(
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            quantity=Decimal("100"),
            avg_cost=Decimal("150"),
            cost_basis=Decimal("15000"),
            realized_pnl=Decimal("0"),
            currency="USD",
            session=session,
        )

    async def test_deletes_and_reinserts_lots(self) -> None:
        repo = AsyncMock()
        projector = PositionProjector(repo)
        session = AsyncMock()

        lot1 = _make_lot()
        lot2 = _make_lot(quantity=Decimal("25"))
        agg = _make_aggregate(lots=[lot1, lot2])

        await projector.project(agg, session=session, currency="EUR")

        # Should have called session.execute (delete) and session.add (2 lots)
        session.execute.assert_called_once()  # delete
        assert session.add.call_count == 2


class TestRebuild:
    async def test_rebuild_replays_events_and_projects(self) -> None:
        repo = AsyncMock()
        projector = PositionProjector(repo)

        event_store = AsyncMock()
        # Return a buy event so the aggregate has state
        trade_event = TradeEvent(
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
        event_store.get_by_aggregate = AsyncMock(return_value=[trade_event])

        mock_session = AsyncMock()
        sf = MagicMock()
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        sf.return_value = session_cm

        aggregate_id = f"{_PORT_ID}:AAPL"

        await projector.rebuild(
            aggregate_id,
            event_store=event_store,
            session_factory=sf,
        )

        event_store.get_by_aggregate.assert_called_once_with(aggregate_id)
        repo.upsert.assert_called_once()
        # Verify upsert was called with correct position data
        call_kwargs = repo.upsert.call_args.kwargs
        assert call_kwargs["portfolio_id"] == _PORT_ID
        assert call_kwargs["instrument_id"] == "AAPL"
        assert call_kwargs["quantity"] == Decimal("100")
        mock_session.commit.assert_called_once()

    async def test_rebuild_empty_events(self) -> None:
        repo = AsyncMock()
        projector = PositionProjector(repo)

        event_store = AsyncMock()
        event_store.get_by_aggregate = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        sf = MagicMock()
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        sf.return_value = session_cm

        aggregate_id = f"{_PORT_ID}:MSFT"

        await projector.rebuild(
            aggregate_id,
            event_store=event_store,
            session_factory=sf,
        )

        # Still upserts (with zero quantity)
        repo.upsert.assert_called_once()
        call_kwargs = repo.upsert.call_args.kwargs
        assert call_kwargs["quantity"] == Decimal("0")
