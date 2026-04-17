"""Unit tests for cash management dependencies, seed, wiring, and settlement core edge cases."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.cash_management.core.settlement import (
    _add_business_days,
    calculate_settlement_date,
    is_business_day,
    snap_to_business_day,
)
from app.modules.cash_management.dependencies import get_cash_service


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestGetCashService:
    def test_returns_service_from_app_state(self):
        service = MagicMock()
        request = MagicMock()
        request.app.state.cash_service = service

        result = get_cash_service(request)
        assert result is service

    def test_raises_503_when_not_initialized(self):
        from fastapi import HTTPException

        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no cash_service attr

        with pytest.raises(HTTPException) as exc_info:
            get_cash_service(request)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Settlement core — calendar-aware branches (lines 50, 72, 85)
# ---------------------------------------------------------------------------


class TestSettlementWithCalendar:
    def test_snap_to_business_day_with_calendar(self):
        """When calendar and country are provided, delegates to calendar."""
        cal = MagicMock()
        cal.next_business_day.return_value = date(2024, 1, 8)

        result = snap_to_business_day(
            date(2024, 1, 6),  # Saturday
            calendar=cal,
            country="US",
        )
        assert result == date(2024, 1, 8)
        cal.next_business_day.assert_called_once_with(date(2024, 1, 6), "US")

    def test_is_business_day_with_calendar(self):
        """When calendar and country are provided, delegates to calendar."""
        cal = MagicMock()
        cal.is_business_day.return_value = False

        result = is_business_day(
            date(2024, 12, 25),
            calendar=cal,
            country="US",
        )
        assert result is False
        cal.is_business_day.assert_called_once_with(date(2024, 12, 25), "US")

    def test_add_business_days_with_calendar(self):
        """When calendar and country are provided, delegates to calendar."""
        cal = MagicMock()
        cal.add_business_days.return_value = date(2024, 1, 10)

        result = _add_business_days(
            date(2024, 1, 8),
            2,
            calendar=cal,
            country="US",
        )
        assert result == date(2024, 1, 10)
        cal.add_business_days.assert_called_once_with(date(2024, 1, 8), 2, "US")

    def test_calculate_settlement_date_with_calendar(self):
        """Full calculate path with a calendar."""
        cal = MagicMock()
        cal.add_business_days.return_value = date(2024, 1, 10)

        result = calculate_settlement_date(
            date(2024, 1, 8),
            "DE",
            calendar=cal,
        )
        assert result == date(2024, 1, 10)
        cal.add_business_days.assert_called_once_with(date(2024, 1, 8), 2, "DE")


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


class TestSeedDevData:
    async def test_skips_when_no_cash_service(self):
        """seed_dev_data returns early when cash_service is not on app.state."""
        from app.modules.cash_management.seed import seed_dev_data

        app = MagicMock()
        app.state = MagicMock(spec=[])  # no cash_service attribute
        sf = MagicMock()

        await seed_dev_data(app, sf)
        # Should not raise — just logs and returns

    async def test_seeds_balances_for_empty_portfolios(self):
        """seed_dev_data credits initial balances for portfolios with no existing balances."""
        from app.modules.cash_management.seed import seed_dev_data

        cash_service = AsyncMock()
        cash_service.get_balances.return_value = []  # no existing balances

        fund = MagicMock()
        fund.id = str(uuid4())
        fund.slug = "alpha"
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [fund]

        portfolio = MagicMock()
        portfolio.id = str(uuid4())
        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund.return_value = [portfolio]

        app = MagicMock()
        app.state.cash_service = cash_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()
        await seed_dev_data(app, sf)

        # Should have credited 2 currencies (EUR, GBP — USD is seeded elsewhere)
        assert cash_service.credit.call_count == 2

    async def test_skips_portfolios_with_existing_balances(self):
        """seed_dev_data skips portfolios that already have balances."""
        from app.modules.cash_management.seed import seed_dev_data

        cash_service = AsyncMock()
        cash_service.get_balances.return_value = [MagicMock()]  # existing

        fund = MagicMock()
        fund.id = str(uuid4())
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [fund]

        portfolio = MagicMock()
        portfolio.id = str(uuid4())
        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund.return_value = [portfolio]

        app = MagicMock()
        app.state.cash_service = cash_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()
        await seed_dev_data(app, sf)

        cash_service.credit.assert_not_called()


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestWiringSetup:
    async def test_wiring_creates_service_and_subscribes(self):
        """setup() wires the service and subscribes to trade events."""
        from app.modules.cash_management.wiring import setup

        app = MagicMock()
        app.state.security_master_service = MagicMock()
        app.state.market_data_service = None

        sf = MagicMock()
        scope_cm = AsyncMock()
        scope_cm.__aenter__ = AsyncMock(return_value=None)
        scope_cm.__aexit__ = AsyncMock(return_value=False)
        sf.fund_scope.return_value = scope_cm

        event_bus = MagicMock()

        fund = MagicMock()
        fund.slug = "alpha"
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [fund]

        with patch.dict("os.environ", {"APP_ENV": "test"}):
            await setup(app, sf, event_bus=event_bus, fund_repo=fund_repo)

        # Should have set cash_service on app.state
        assert hasattr(app.state, "cash_service")
        # Should have subscribed to trades.executed for each active fund
        event_bus.subscribe.assert_called_once()
        topic_arg = event_bus.subscribe.call_args[0][0]
        assert "trades.executed" in topic_arg

    async def test_wiring_with_local_env_runs_seed(self):
        """When APP_ENV=local, seed_dev_data is invoked."""
        from app.modules.cash_management.wiring import setup

        app = MagicMock()
        app.state.security_master_service = MagicMock()
        app.state.market_data_service = None

        sf = MagicMock()
        event_bus = MagicMock()

        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = []

        with (
            patch.dict("os.environ", {"APP_ENV": "local"}),
            patch("app.modules.cash_management.seed.seed_dev_data") as mock_seed,
        ):
            mock_seed.return_value = None

            await setup(app, sf, event_bus=event_bus, fund_repo=fund_repo)

            mock_seed.assert_called_once()


# ---------------------------------------------------------------------------
# Repositories __init__ — import coverage
# ---------------------------------------------------------------------------


class TestRepositoryReexports:
    def test_all_repos_importable(self):
        from app.modules.cash_management.repositories import (
            CashBalanceRepository,
            CashJournalRepository,
            CashProjectionRepository,
            ScheduledFlowRepository,
            SettlementRepository,
        )

        assert CashBalanceRepository is not None
        assert CashJournalRepository is not None
        assert CashProjectionRepository is not None
        assert ScheduledFlowRepository is not None
        assert SettlementRepository is not None
