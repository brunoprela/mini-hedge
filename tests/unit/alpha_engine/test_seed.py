"""Unit tests for alpha engine seed module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.alpha_engine.seed import seed_dev_data


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_skips_when_service_not_available(self) -> None:
        app = MagicMock()
        app.state.alpha_service = None

        sf = MagicMock()

        # getattr returns None -> early return
        await seed_dev_data(app, sf)

    @pytest.mark.asyncio
    async def test_skips_when_service_attr_missing(self) -> None:
        class FakeState:
            pass

        app = MagicMock()
        app.state = FakeState()
        sf = MagicMock()

        await seed_dev_data(app, sf)

    @pytest.mark.asyncio
    async def test_seeds_scenarios_and_optimization(self) -> None:
        pid = str(uuid4())

        mock_fund = MagicMock()
        mock_fund.id = "fund-1"

        mock_portfolio = MagicMock()
        mock_portfolio.id = pid

        scenario_repo = AsyncMock()
        scenario_repo.get_many = AsyncMock(return_value=[])  # not already seeded
        scenario_repo.save = AsyncMock()

        opt_run_repo = AsyncMock()
        opt_run_repo.save = AsyncMock()

        opt_weight_repo = AsyncMock()
        opt_weight_repo.save_many = AsyncMock()

        intent_repo = AsyncMock()
        intent_repo.save_many = AsyncMock()

        alpha_service = MagicMock()
        alpha_service._scenario_repo = scenario_repo
        alpha_service._opt_run_repo = opt_run_repo
        alpha_service._opt_weight_repo = opt_weight_repo
        alpha_service._intent_repo = intent_repo

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[mock_portfolio])

        app = MagicMock()
        app.state.alpha_service = alpha_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        # 2 scenarios seeded (_SCENARIOS has 2 entries)
        assert scenario_repo.save.call_count == 2
        # 1 optimization run
        opt_run_repo.save.assert_called_once()
        # weights and intents saved
        opt_weight_repo.save_many.assert_called_once()
        intent_repo.save_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_already_seeded(self) -> None:
        mock_fund = MagicMock()
        mock_fund.id = "fund-1"

        mock_portfolio = MagicMock()
        mock_portfolio.id = str(uuid4())

        scenario_repo = AsyncMock()
        scenario_repo.get_many = AsyncMock(return_value=[MagicMock()])  # already exists
        scenario_repo.save = AsyncMock()

        alpha_service = MagicMock()
        alpha_service._scenario_repo = scenario_repo
        alpha_service._opt_run_repo = AsyncMock()
        alpha_service._opt_weight_repo = AsyncMock()
        alpha_service._intent_repo = AsyncMock()

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[mock_portfolio])

        app = MagicMock()
        app.state.alpha_service = alpha_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        scenario_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_fund_with_no_portfolios(self) -> None:
        mock_fund = MagicMock()
        mock_fund.id = "fund-1"

        scenario_repo = AsyncMock()
        scenario_repo.save = AsyncMock()

        alpha_service = MagicMock()
        alpha_service._scenario_repo = scenario_repo
        alpha_service._opt_run_repo = AsyncMock()
        alpha_service._opt_weight_repo = AsyncMock()
        alpha_service._intent_repo = AsyncMock()

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[])  # no portfolios

        app = MagicMock()
        app.state.alpha_service = alpha_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        scenario_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_seeds_correct_number_of_weights_and_intents(self) -> None:
        """Verify weight and intent record counts match the template data."""
        pid = str(uuid4())

        mock_fund = MagicMock()
        mock_fund.id = "fund-1"

        mock_portfolio = MagicMock()
        mock_portfolio.id = pid

        scenario_repo = AsyncMock()
        scenario_repo.get_many = AsyncMock(return_value=[])
        scenario_repo.save = AsyncMock()

        opt_run_repo = AsyncMock()
        opt_run_repo.save = AsyncMock()

        saved_weights = []
        saved_intents = []

        async def capture_weights(records, **kwargs):
            saved_weights.extend(records)

        async def capture_intents(records, **kwargs):
            saved_intents.extend(records)

        opt_weight_repo = AsyncMock()
        opt_weight_repo.save_many = AsyncMock(side_effect=capture_weights)

        intent_repo = AsyncMock()
        intent_repo.save_many = AsyncMock(side_effect=capture_intents)

        alpha_service = MagicMock()
        alpha_service._scenario_repo = scenario_repo
        alpha_service._opt_run_repo = opt_run_repo
        alpha_service._opt_weight_repo = opt_weight_repo
        alpha_service._intent_repo = intent_repo

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[mock_portfolio])

        app = MagicMock()
        app.state.alpha_service = alpha_service
        app.state.fund_repo = fund_repo
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()

        await seed_dev_data(app, sf)

        # _OPT_WEIGHTS has 6 entries
        assert len(saved_weights) == 6
        # All 6 have non-zero delta, so 6 intents
        assert len(saved_intents) == 6
