"""Unit tests for CashManagementService.handle_trade_executed — tested in isolation."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.cash_management.service import CashManagementService
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import fund_topic
from tests.factories import make_trades_executed_event
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
            fund_topic("alpha", "cash.settlement.created"),
            fund_topic("alpha", "cash.settlement.settled"),
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
def service(
    mock_session_factory: MagicMock,
    event_bus: InProcessEventBus,
) -> CashManagementService:
    return CashManagementService(
        session_factory=mock_session_factory,
        balance_repo=AsyncMock(),
        journal_repo=AsyncMock(),
        settlement_repo=AsyncMock(),
        scheduled_flow_repo=AsyncMock(),
        projection_repo=AsyncMock(),
        security_master_service=AsyncMock(),
        event_bus=event_bus,
    )


class TestHandleTradeExecuted:
    """Tests for CashManagementService.handle_trade_executed."""

    async def test_buy_creates_negative_settlement(
        self,
        service: CashManagementService,
    ) -> None:
        """A buy trade should create a cash outflow (negative amount)."""
        event = make_trades_executed_event(
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )

        with AsyncMock() as mock_create:
            service.create_settlement = mock_create
            await service.handle_trade_executed(event)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            # Buy: amount = -(quantity * price) = -15000
            assert call_kwargs.kwargs["amount"] == Decimal("-15000.00")

    async def test_sell_creates_positive_settlement(
        self,
        service: CashManagementService,
    ) -> None:
        """A sell trade should create a cash inflow (positive amount)."""
        event = make_trades_executed_event(
            side="sell",
            quantity=Decimal("50"),
            price=Decimal("200.00"),
        )

        with AsyncMock() as mock_create:
            service.create_settlement = mock_create
            await service.handle_trade_executed(event)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            # Sell: amount = quantity * price = 10000
            assert call_kwargs.kwargs["amount"] == Decimal("10000.00")

    async def test_missing_portfolio_id_is_noop(
        self,
        service: CashManagementService,
    ) -> None:
        """When portfolio_id is missing from event data, handler returns early."""
        event = make_trades_executed_event()
        bad_data = {k: v for k, v in event.data.items() if k != "portfolio_id"}
        bad_event = event.model_copy(update={"data": bad_data})

        service.create_settlement = AsyncMock()
        await service.handle_trade_executed(bad_event)

        service.create_settlement.assert_not_called()

    async def test_fund_scope_is_set(
        self,
        service: CashManagementService,
        mock_session_factory: MagicMock,
    ) -> None:
        """Handler should set fund_scope from event.fund_slug."""
        event = make_trades_executed_event(fund_slug="alpha")

        service.create_settlement = AsyncMock()
        await service.handle_trade_executed(event)

        mock_session_factory.fund_scope.assert_called_once_with("alpha")

    async def test_handler_error_is_caught(
        self,
        service: CashManagementService,
    ) -> None:
        """Exceptions in the handler should be caught and logged, not propagated."""
        event = make_trades_executed_event()

        # Make create_settlement raise
        service.create_settlement = AsyncMock(side_effect=RuntimeError("DB error"))

        # Should not propagate
        await service.handle_trade_executed(event)

    async def test_currency_defaults_to_usd(
        self,
        service: CashManagementService,
    ) -> None:
        """When currency is missing from event data, defaults to USD."""
        event = make_trades_executed_event()
        data = dict(event.data)
        del data["currency"]
        event = event.model_copy(update={"data": data})

        service.create_settlement = AsyncMock()
        await service.handle_trade_executed(event)

        call_kwargs = service.create_settlement.call_args
        assert call_kwargs.kwargs["currency"] == "USD"
