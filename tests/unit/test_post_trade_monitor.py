"""Unit tests for PostTradeMonitor event handlers — tested in isolation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.compliance.post_trade import PostTradeMonitor
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import fund_topic
from tests.factories import DEFAULT_PORTFOLIO_ID, make_base_event
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
            fund_topic("alpha", "compliance.violations"),
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
def mock_rule_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_active.return_value = []  # No rules by default
    return repo


@pytest.fixture
def mock_violation_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_by_portfolio.return_value = []
    return repo


@pytest.fixture
def mock_position_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_portfolio.return_value = []
    return repo


@pytest.fixture
def monitor(
    mock_session_factory: MagicMock,
    mock_rule_repo: AsyncMock,
    mock_violation_repo: AsyncMock,
    mock_position_repo: AsyncMock,
    event_bus: InProcessEventBus,
) -> PostTradeMonitor:
    return PostTradeMonitor(
        session_factory=mock_session_factory,
        rule_repo=mock_rule_repo,
        violation_repo=mock_violation_repo,
        position_repo=mock_position_repo,
        security_master=None,
        event_bus=event_bus,
        cash_balance_repo=None,
    )


def _position_changed_event(
    portfolio_id: UUID = DEFAULT_PORTFOLIO_ID,
    fund_slug: str = "alpha",
) -> MagicMock:
    """Build a positions.changed BaseEvent."""
    return make_base_event(
        event_type="position.changed",
        data={
            "portfolio_id": str(portfolio_id),
            "instrument_id": "AAPL",
            "quantity": "100",
            "avg_cost": "150.00",
            "cost_basis": "15000.00",
            "currency": "USD",
        },
        fund_slug=fund_slug,
    )


def _pnl_updated_event(
    portfolio_id: UUID = DEFAULT_PORTFOLIO_ID,
    fund_slug: str = "alpha",
) -> MagicMock:
    """Build a pnl.updated BaseEvent."""
    return make_base_event(
        event_type="pnl.mark_to_market",
        data={
            "portfolio_id": str(portfolio_id),
            "instrument_id": "AAPL",
            "market_price": "160.00",
            "market_value": "16000.00",
            "unrealized_pnl": "1000.00",
            "pnl_change": "500.00",
            "currency": "USD",
        },
        fund_slug=fund_slug,
    )


class TestHandlePositionChanged:
    """Tests for PostTradeMonitor.handle_position_changed."""

    async def test_no_rules_is_noop(
        self,
        monitor: PostTradeMonitor,
        mock_rule_repo: AsyncMock,
        capture: EventCapture,
    ) -> None:
        """When no compliance rules exist, the handler is a pass-through."""
        mock_rule_repo.get_active.return_value = []
        event = _position_changed_event()

        await monitor.handle_position_changed(event)

        # No violations should be published
        assert len(capture.events) == 0

    async def test_missing_portfolio_id_is_silent_return(
        self,
        monitor: PostTradeMonitor,
        mock_rule_repo: AsyncMock,
    ) -> None:
        """When portfolio_id is missing from event data, handler returns silently."""
        event = make_base_event(
            event_type="position.changed",
            data={"instrument_id": "AAPL"},  # no portfolio_id
            fund_slug="alpha",
        )

        # Should not raise
        await monitor.handle_position_changed(event)

        # _evaluate_portfolio should never be called
        mock_rule_repo.get_active.assert_not_called()

    async def test_missing_fund_slug_is_silent_return(
        self,
        monitor: PostTradeMonitor,
        mock_rule_repo: AsyncMock,
    ) -> None:
        """When fund_slug is None on the event, handler returns silently."""
        event = make_base_event(
            event_type="position.changed",
            data={"portfolio_id": str(DEFAULT_PORTFOLIO_ID)},
            fund_slug=None,  # type: ignore[arg-type]
        )
        # BaseEvent has fund_slug as str | None, but make_base_event defaults to "alpha"
        # We need to explicitly set it to None
        event = event.model_copy(update={"fund_slug": None})

        await monitor.handle_position_changed(event)

        mock_rule_repo.get_active.assert_not_called()

    async def test_calls_evaluate_with_is_passive_false(
        self,
        monitor: PostTradeMonitor,
        mock_session_factory: MagicMock,
    ) -> None:
        """handle_position_changed calls _evaluate_portfolio with is_passive=False."""
        event = _position_changed_event()

        with AsyncMock() as mock_eval:
            monitor._evaluate_portfolio = mock_eval
            await monitor.handle_position_changed(event)

            mock_eval.assert_called_once_with(
                DEFAULT_PORTFOLIO_ID,
                "alpha",
                is_passive=False,
            )

    async def test_handler_error_is_caught(
        self,
        monitor: PostTradeMonitor,
        mock_session_factory: MagicMock,
    ) -> None:
        """Exceptions in _evaluate_portfolio are caught and logged."""
        event = _position_changed_event()

        monitor._evaluate_portfolio = AsyncMock(side_effect=RuntimeError("DB error"))

        # Should not propagate
        await monitor.handle_position_changed(event)


class TestHandleMtmUpdate:
    """Tests for PostTradeMonitor.handle_mtm_update."""

    async def test_calls_evaluate_with_is_passive_true(
        self,
        monitor: PostTradeMonitor,
    ) -> None:
        """handle_mtm_update calls _evaluate_portfolio with is_passive=True."""
        event = _pnl_updated_event()

        with AsyncMock() as mock_eval:
            monitor._evaluate_portfolio = mock_eval
            await monitor.handle_mtm_update(event)

            mock_eval.assert_called_once_with(
                DEFAULT_PORTFOLIO_ID,
                "alpha",
                is_passive=True,
            )

    async def test_missing_portfolio_id_is_silent_return(
        self,
        monitor: PostTradeMonitor,
        mock_rule_repo: AsyncMock,
    ) -> None:
        """When portfolio_id is missing, handler returns silently."""
        event = make_base_event(
            event_type="pnl.mark_to_market",
            data={"instrument_id": "AAPL"},
            fund_slug="alpha",
        )

        await monitor.handle_mtm_update(event)
        mock_rule_repo.get_active.assert_not_called()

    async def test_handler_error_is_caught(
        self,
        monitor: PostTradeMonitor,
    ) -> None:
        """Exceptions are caught and logged."""
        event = _pnl_updated_event()
        monitor._evaluate_portfolio = AsyncMock(side_effect=RuntimeError("DB error"))

        await monitor.handle_mtm_update(event)
