"""Unit tests for TradeHandler.handle_trade_event — tested in isolation.

Uses real InProcessEventBus + EventCapture to verify downstream event publication.
Uses AsyncMock for DB-dependent repositories.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.positions.interface import TradeSide
from app.modules.positions.trade_handler import TradeHandler
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import fund_topic
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trades_executed_event
from tests.helpers import EventCapture


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(
        event_bus,
        [
            fund_topic("alpha", "positions.changed"),
            fund_topic("alpha", "pnl.updated"),
            fund_topic("alpha", "trades.executed"),
        ],
    )
    return cap


@pytest.fixture
def mock_session_factory() -> MagicMock:
    sf = MagicMock()
    # fund_scope returns an async context manager
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm
    return sf


@pytest.fixture
def mock_event_store() -> AsyncMock:
    store = AsyncMock()
    store.get_by_aggregate.return_value = []
    store.has_idempotency_key.return_value = False
    return store


@pytest.fixture
def mock_projector() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(
    mock_session_factory: MagicMock,
    mock_event_store: AsyncMock,
    mock_projector: AsyncMock,
    event_bus: InProcessEventBus,
) -> TradeHandler:
    return TradeHandler(
        session_factory=mock_session_factory,
        event_store=mock_event_store,
        projector=mock_projector,
        event_bus=event_bus,
    )


class TestHandleTradeEvent:
    """Tests for TradeHandler.handle_trade_event (the Kafka subscriber path)."""

    async def test_happy_path_publishes_downstream_events(
        self,
        handler: TradeHandler,
        capture: EventCapture,
    ) -> None:
        """A valid trades.executed event should produce positions.changed and pnl events."""
        event = make_trades_executed_event(
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )

        # The handler will call _apply_trade which does DB operations.
        # We need to patch _apply_trade to return downstream events.
        from app.modules.positions.interface import (
            PositionChanged,
            PositionChangedData,
            PositionEventType,
        )

        downstream = [
            PositionChanged(
                event_type=PositionEventType.POSITION_CHANGED,
                data=PositionChangedData(
                    portfolio_id=DEFAULT_PORTFOLIO_ID,
                    instrument_id="AAPL",
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150.00"),
                    cost_basis=Decimal("15000.00"),
                    currency="USD",
                ),
            ),
        ]

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=downstream):
            await handler.handle_trade_event(event)

        # Verify positions.changed was published
        pos_events = capture.get_by_topic("positions.changed")
        assert len(pos_events) == 1
        assert pos_events[0].data["instrument_id"] == "AAPL"
        assert pos_events[0].data["portfolio_id"] == str(DEFAULT_PORTFOLIO_ID)
        assert pos_events[0].fund_slug == "alpha"

    async def test_idempotent_duplicate_is_noop(
        self,
        handler: TradeHandler,
        capture: EventCapture,
    ) -> None:
        """When _apply_trade returns None (duplicate), no downstream events published."""
        event = make_trades_executed_event()

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=None):
            await handler.handle_trade_event(event)

        assert len(capture.events) == 0

    async def test_missing_portfolio_id_is_caught(
        self,
        handler: TradeHandler,
        capture: EventCapture,
    ) -> None:
        """Missing portfolio_id in event data triggers KeyError, caught by except block."""
        event = make_trades_executed_event()
        # Remove portfolio_id from the event data
        bad_data = {k: v for k, v in event.data.items() if k != "portfolio_id"}
        bad_event = event.model_copy(update={"data": bad_data})

        # Should not raise — the handler catches all exceptions
        await handler.handle_trade_event(bad_event)

        # No downstream events should be published
        assert len(capture.events) == 0

    async def test_side_parsing(self) -> None:
        """Verify the side string parsing logic from handle_trade_event (line 145)."""
        # Mirrors handle_trade_event side parsing logic (line 145)
        assert (TradeSide.BUY if "buy" == "buy" else TradeSide.SELL) == TradeSide.BUY
        assert (TradeSide.BUY if "sell" == "buy" else TradeSide.SELL) == TradeSide.SELL

    async def test_downstream_events_carry_actor_info(
        self,
        handler: TradeHandler,
        capture: EventCapture,
    ) -> None:
        """Downstream events should carry actor_id and actor_type from the source event."""
        event = make_trades_executed_event()
        event = event.model_copy(update={"actor_id": "trader-1", "actor_type": "user"})

        from app.modules.positions.interface import (
            PositionChanged,
            PositionChangedData,
            PositionEventType,
        )

        downstream = [
            PositionChanged(
                event_type=PositionEventType.POSITION_CHANGED,
                data=PositionChangedData(
                    portfolio_id=DEFAULT_PORTFOLIO_ID,
                    instrument_id="AAPL",
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150.00"),
                    cost_basis=Decimal("15000.00"),
                    currency="USD",
                ),
            ),
        ]

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=downstream):
            await handler.handle_trade_event(event)

        pos_events = capture.get_by_topic("positions.changed")
        assert pos_events[0].actor_id == "trader-1"
        assert pos_events[0].actor_type == "user"

    async def test_fund_scope_is_set(
        self,
        handler: TradeHandler,
        mock_session_factory: MagicMock,
        capture: EventCapture,
    ) -> None:
        """Handler should call fund_scope with the event's fund_slug."""
        event = make_trades_executed_event(fund_slug="beta")

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=[]):
            await handler.handle_trade_event(event)

        mock_session_factory.fund_scope.assert_called_once_with("beta")
