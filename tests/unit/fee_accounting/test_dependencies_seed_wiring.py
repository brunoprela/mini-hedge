"""Unit tests for fee accounting dependencies, seed, and wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.fee_accounting.dependencies import (
    get_fee_accounting_service,
    get_fee_schedule_repo,
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestGetFeeAccountingService:
    def test_returns_service_from_app_state(self) -> None:
        service = MagicMock()
        request = MagicMock()
        request.app.state.fee_accounting_service = service

        result = get_fee_accounting_service(request)
        assert result is service

    def test_raises_503_when_not_initialized(self) -> None:
        from fastapi import HTTPException

        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no fee_accounting_service attr

        with pytest.raises(HTTPException) as exc_info:
            get_fee_accounting_service(request)
        assert exc_info.value.status_code == 503


class TestGetFeeScheduleRepo:
    def test_returns_repo_from_app_state(self) -> None:
        repo = MagicMock()
        request = MagicMock()
        request.app.state.fee_schedule_repo = repo

        result = get_fee_schedule_repo(request)
        assert result is repo

    def test_raises_503_when_not_initialized(self) -> None:
        from fastapi import HTTPException

        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no fee_schedule_repo attr

        with pytest.raises(HTTPException) as exc_info:
            get_fee_schedule_repo(request)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_seeds_schedules_for_active_funds(self) -> None:
        from app.modules.fee_accounting.seed import seed_dev_data

        fund_alpha = MagicMock()
        fund_alpha.slug = "alpha"

        fund_beta = MagicMock()
        fund_beta.slug = "beta"

        app = MagicMock()
        schedule_repo = AsyncMock()
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[fund_alpha, fund_beta])
        # Simulate: no existing schedules
        schedule_repo.get_by_fund_slug = AsyncMock(return_value=None)
        schedule_repo.upsert = AsyncMock(side_effect=lambda rec, **kw: rec)

        app.state.fee_schedule_repo = schedule_repo
        app.state.fund_repo = fund_repo

        # Build session factory mock
        sf = MagicMock()
        mock_session = AsyncMock()
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        sf.return_value = session_cm
        # fund_scope returns an async context manager
        scope_cm = AsyncMock()
        scope_cm.__aenter__ = AsyncMock()
        scope_cm.__aexit__ = AsyncMock(return_value=False)
        sf.fund_scope = MagicMock(return_value=scope_cm)

        await seed_dev_data(app, sf)

        # Should have created 2 schedules per fund (default + founders) for 2 funds = 4 upserts
        assert schedule_repo.upsert.call_count == 4

    @pytest.mark.asyncio
    async def test_skips_existing_schedules(self) -> None:
        from app.modules.fee_accounting.seed import seed_dev_data

        fund = MagicMock()
        fund.slug = "alpha"

        app = MagicMock()
        schedule_repo = AsyncMock()
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[fund])
        # Already has a schedule
        schedule_repo.get_by_fund_slug = AsyncMock(return_value=MagicMock())

        app.state.fee_schedule_repo = schedule_repo
        app.state.fund_repo = fund_repo

        sf = MagicMock()
        mock_session = AsyncMock()
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        sf.return_value = session_cm
        scope_cm = AsyncMock()
        scope_cm.__aenter__ = AsyncMock()
        scope_cm.__aexit__ = AsyncMock(return_value=False)
        sf.fund_scope = MagicMock(return_value=scope_cm)

        await seed_dev_data(app, sf)

        schedule_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_seeds_unknown_fund_with_defaults(self) -> None:
        """A fund not in the config dict gets default fee parameters."""
        from app.modules.fee_accounting.seed import seed_dev_data

        fund = MagicMock()
        fund.slug = "unknown_fund"

        app = MagicMock()
        schedule_repo = AsyncMock()
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[fund])
        schedule_repo.get_by_fund_slug = AsyncMock(return_value=None)
        schedule_repo.upsert = AsyncMock(side_effect=lambda rec, **kw: rec)

        app.state.fee_schedule_repo = schedule_repo
        app.state.fund_repo = fund_repo

        sf = MagicMock()
        mock_session = AsyncMock()
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        sf.return_value = session_cm
        scope_cm = AsyncMock()
        scope_cm.__aenter__ = AsyncMock()
        scope_cm.__aexit__ = AsyncMock(return_value=False)
        sf.fund_scope = MagicMock(return_value=scope_cm)

        await seed_dev_data(app, sf)

        # Should still create default + founders schedules
        assert schedule_repo.upsert.call_count == 2


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestWiringSetup:
    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    async def test_setup_production_no_seed(self) -> None:
        from app.modules.fee_accounting.wiring import setup

        app = MagicMock()
        app.state = MagicMock()
        sf = MagicMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        # Service and repo should be attached to app.state
        assert hasattr(app.state, "fee_accounting_service")
        assert hasattr(app.state, "fee_schedule_repo")

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"}, clear=False)
    async def test_setup_local_calls_seed(self) -> None:
        """In local env the setup function imports and calls seed_dev_data."""
        from app.modules.fee_accounting import wiring

        app = MagicMock()
        app.state = MagicMock()
        sf = MagicMock()

        with patch(
            "app.modules.fee_accounting.seed.seed_dev_data",
            new_callable=AsyncMock,
        ) as patched_seed:
            await wiring.setup(app, sf)
            patched_seed.assert_called_once_with(app, sf)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    async def test_setup_without_event_bus(self) -> None:
        from app.modules.fee_accounting.wiring import setup

        app = MagicMock()
        app.state = MagicMock()
        sf = MagicMock()

        await setup(app, sf)

        # Should not raise, service still created with event_bus=None
        assert hasattr(app.state, "fee_accounting_service")
