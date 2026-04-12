"""Unit tests for exposure seed module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_skips_when_service_not_available(self) -> None:
        from app.modules.exposure.seed import seed_dev_data

        app = MagicMock()
        app.state.exposure_service = None

        sf = MagicMock()

        # Should return early without error
        await seed_dev_data(app, sf)

    @pytest.mark.asyncio
    async def test_skips_when_service_attr_missing(self) -> None:
        from app.modules.exposure.seed import seed_dev_data

        class FakeState:
            pass

        app = MagicMock()
        app.state = FakeState()
        sf = MagicMock()

        await seed_dev_data(app, sf)

    @pytest.mark.asyncio
    async def test_seeds_snapshots_for_portfolios(self) -> None:
        from app.modules.exposure.seed import seed_dev_data

        mock_fund = MagicMock()
        mock_fund.id = "fund-1"
        mock_fund.slug = "alpha"

        mock_portfolio = MagicMock()
        mock_portfolio.id = str(uuid4())

        exposure_repo = AsyncMock()
        exposure_repo.get_latest = AsyncMock(return_value=None)
        exposure_repo.save_snapshot = AsyncMock()

        exposure_service = MagicMock()
        exposure_service._exposure_repo = exposure_repo

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[mock_portfolio])

        app = MagicMock()
        app.state.exposure_service = exposure_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        # 3 days of snapshots for 1 portfolio
        assert exposure_repo.save_snapshot.call_count == 3

    @pytest.mark.asyncio
    async def test_skips_portfolio_with_existing_snapshot(self) -> None:
        from app.modules.exposure.seed import seed_dev_data

        mock_fund = MagicMock()
        mock_fund.id = "fund-1"
        mock_fund.slug = "alpha"

        mock_portfolio = MagicMock()
        mock_portfolio.id = str(uuid4())

        exposure_repo = AsyncMock()
        exposure_repo.get_latest = AsyncMock(return_value=MagicMock())  # existing
        exposure_repo.save_snapshot = AsyncMock()

        exposure_service = MagicMock()
        exposure_service._exposure_repo = exposure_repo

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[mock_portfolio])

        app = MagicMock()
        app.state.exposure_service = exposure_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        exposure_repo.save_snapshot.assert_not_called()
