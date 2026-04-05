"""Unit tests for MarkToMarketHandler.handle_price_update — tested in isolation."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.positions.mtm_handler import MarkToMarketHandler
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import fund_topic
from app.shared.types import AssetClass
from tests.factories import make_price_event
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
            fund_topic("alpha", "pnl.updated"),
            fund_topic("beta", "pnl.updated"),
        ],
    )
    return cap


@pytest.fixture
def mock_session_factory() -> MagicMock:
    sf = MagicMock()
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm
    return sf


@pytest.fixture
def handler(
    mock_session_factory: MagicMock,
    event_bus: InProcessEventBus,
) -> MarkToMarketHandler:
    async def get_fund_slugs() -> list[str]:
        return ["alpha"]

    async def get_asset_class(instrument_id: str) -> AssetClass | None:
        return AssetClass.EQUITY

    return MarkToMarketHandler(
        session_factory=mock_session_factory,
        event_bus=event_bus,
        get_fund_slugs=get_fund_slugs,
        get_asset_class=get_asset_class,
    )


class TestHandlePriceUpdate:
    """Tests for MarkToMarketHandler.handle_price_update."""

    async def test_unknown_instrument_is_skipped(
        self,
        mock_session_factory: MagicMock,
        event_bus: InProcessEventBus,
        capture: EventCapture,
    ) -> None:
        """When get_asset_class returns None, handler skips processing."""

        async def get_asset_class(_: str) -> AssetClass | None:
            return None

        h = MarkToMarketHandler(
            session_factory=mock_session_factory,
            event_bus=event_bus,
            get_fund_slugs=AsyncMock(return_value=["alpha"]),
            get_asset_class=get_asset_class,
        )

        event = make_price_event(instrument_id="UNKNOWN")
        await h.handle_price_update(event)

        assert len(capture.events) == 0

    async def test_no_positions_no_events(
        self,
        handler: MarkToMarketHandler,
        capture: EventCapture,
    ) -> None:
        """When no positions hold the instrument, no pnl.updated events are published."""
        with patch("app.modules.positions.mtm_handler.CurrentPositionRepository") as mock_repo_cls:
            instance = mock_repo_cls.return_value
            instance.get_by_instrument = AsyncMock(return_value=[])

            event = make_price_event(instrument_id="AAPL")
            await handler.handle_price_update(event)

        assert len(capture.events) == 0

    async def test_price_update_publishes_pnl_event(
        self,
        handler: MarkToMarketHandler,
        capture: EventCapture,
    ) -> None:
        """When position exists and price change exceeds threshold, pnl.updated is published."""
        # Create a mock position record
        mock_pos = MagicMock()
        mock_pos.portfolio_id = "11111111-1111-1111-1111-111111111111"
        mock_pos.instrument_id = "AAPL"
        mock_pos.quantity = Decimal("100")
        mock_pos.cost_basis = Decimal("15000.00")
        mock_pos.market_price = Decimal("150.00")
        mock_pos.market_value = Decimal("15000.00")
        mock_pos.unrealized_pnl = Decimal("0.00")
        mock_pos.currency = "USD"

        with patch("app.modules.positions.mtm_handler.CurrentPositionRepository") as mock_repo_cls:
            instance = mock_repo_cls.return_value
            instance.get_by_instrument = AsyncMock(return_value=[mock_pos])
            instance.update_market_value = AsyncMock()

            # Price moves from 150 to 200 (large change, above threshold)
            event = make_price_event(instrument_id="AAPL", mid=Decimal("200.00"))
            await handler.handle_price_update(event)

        # Should have updated the position
        instance.update_market_value.assert_called_once()

        # Should have published pnl.updated
        pnl_events = capture.get_by_topic("pnl.updated")
        assert len(pnl_events) == 1
        assert pnl_events[0].data["instrument_id"] == "AAPL"
        assert pnl_events[0].fund_slug == "alpha"
        assert pnl_events[0].actor_id == "system"

    async def test_noise_filter_suppresses_tiny_changes(
        self,
        handler: MarkToMarketHandler,
        capture: EventCapture,
    ) -> None:
        """Price changes below 0.01% of market value don't publish pnl events."""
        mock_pos = MagicMock()
        mock_pos.portfolio_id = "11111111-1111-1111-1111-111111111111"
        mock_pos.instrument_id = "AAPL"
        mock_pos.quantity = Decimal("100")
        mock_pos.cost_basis = Decimal("15000.00")
        mock_pos.market_price = Decimal("150.00")
        mock_pos.market_value = Decimal("15000.00")
        mock_pos.unrealized_pnl = Decimal("0.00")
        mock_pos.currency = "USD"

        with patch("app.modules.positions.mtm_handler.CurrentPositionRepository") as mock_repo_cls:
            instance = mock_repo_cls.return_value
            instance.get_by_instrument = AsyncMock(return_value=[mock_pos])
            instance.update_market_value = AsyncMock()

            # Price moves from 150 to 150.001 (tiny change, below threshold)
            event = make_price_event(instrument_id="AAPL", mid=Decimal("150.001"))
            await handler.handle_price_update(event)

        # Position should still be updated
        instance.update_market_value.assert_called_once()

        # But no pnl event should be published (noise filter)
        assert len(capture.events) == 0

    async def test_multi_fund_iteration(
        self,
        mock_session_factory: MagicMock,
        event_bus: InProcessEventBus,
        capture: EventCapture,
    ) -> None:
        """Handler should iterate all fund slugs and update each fund's positions."""

        async def get_fund_slugs() -> list[str]:
            return ["alpha", "beta"]

        h = MarkToMarketHandler(
            session_factory=mock_session_factory,
            event_bus=event_bus,
            get_fund_slugs=get_fund_slugs,
            get_asset_class=AsyncMock(return_value=AssetClass.EQUITY),
        )

        mock_pos = MagicMock()
        mock_pos.portfolio_id = "11111111-1111-1111-1111-111111111111"
        mock_pos.instrument_id = "AAPL"
        mock_pos.quantity = Decimal("100")
        mock_pos.cost_basis = Decimal("15000.00")
        mock_pos.market_price = Decimal("150.00")
        mock_pos.market_value = Decimal("15000.00")
        mock_pos.unrealized_pnl = Decimal("0.00")
        mock_pos.currency = "USD"

        with patch("app.modules.positions.mtm_handler.CurrentPositionRepository") as mock_repo_cls:
            instance = mock_repo_cls.return_value
            instance.get_by_instrument = AsyncMock(return_value=[mock_pos])
            instance.update_market_value = AsyncMock()

            event = make_price_event(instrument_id="AAPL", mid=Decimal("200.00"))
            await h.handle_price_update(event)

        # fund_scope should be called twice (alpha and beta)
        assert mock_session_factory.fund_scope.call_count == 2

    async def test_handler_error_is_caught(
        self,
        handler: MarkToMarketHandler,
        capture: EventCapture,
    ) -> None:
        """Exceptions in handler are caught and logged, not propagated."""
        # Missing 'mid' field will cause Decimal parsing error
        bad_event = make_price_event()
        bad_data = {k: v for k, v in bad_event.data.items() if k != "mid"}
        bad_event = bad_event.model_copy(update={"data": bad_data})

        # Should not raise
        await handler.handle_price_update(bad_event)
        assert len(capture.events) == 0
