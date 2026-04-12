"""Unit tests for FX hedging seed module."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.fx_hedging.seed import seed_dev_data


def _make_fund(slug: str) -> MagicMock:
    f = MagicMock()
    f.slug = slug
    return f


class _FakeSF:
    """Fake TenantSessionFactory supporting fund_scope + __call__ as async ctx mgrs."""

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    def fund_scope(self, slug: str):
        @asynccontextmanager
        async def _ctx():
            yield

        return _ctx()

    def __call__(self):
        session = self._session

        @asynccontextmanager
        async def _ctx():
            yield session

        return _ctx()


class TestSeedDevData:
    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.repositories.FXForwardRepository")
    @patch("app.modules.fx_hedging.repositories.FXInterestRateRepository")
    async def test_seeds_rates_when_none_exist(
        self, MockRateRepo: MagicMock, MockFwdRepo: MagicMock
    ) -> None:
        app = MagicMock()
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("alpha")])
        app.state.fund_repo = fund_repo

        rate_repo = AsyncMock()
        rate_repo.get_all = AsyncMock(return_value=[])
        rate_repo.upsert = AsyncMock()
        MockRateRepo.return_value = rate_repo

        forward_repo = AsyncMock()
        forward_repo.get_by_portfolio = AsyncMock(return_value=[])
        forward_repo.create = AsyncMock()
        MockFwdRepo.return_value = forward_repo

        session = AsyncMock()

        await seed_dev_data(app, _FakeSF(session))

        # Rates should have been seeded (7 currencies)
        assert rate_repo.upsert.call_count == 7

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.repositories.FXForwardRepository")
    @patch("app.modules.fx_hedging.repositories.FXInterestRateRepository")
    async def test_skips_rates_when_already_exist(
        self, MockRateRepo: MagicMock, MockFwdRepo: MagicMock
    ) -> None:
        app = MagicMock()
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("alpha")])
        app.state.fund_repo = fund_repo

        rate_repo = AsyncMock()
        rate_repo.get_all = AsyncMock(return_value=[MagicMock()])
        MockRateRepo.return_value = rate_repo

        forward_repo = AsyncMock()
        forward_repo.get_by_portfolio = AsyncMock(return_value=[])
        forward_repo.create = AsyncMock()
        MockFwdRepo.return_value = forward_repo

        session = AsyncMock()

        await seed_dev_data(app, _FakeSF(session))

        rate_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.repositories.FXForwardRepository")
    @patch("app.modules.fx_hedging.repositories.FXInterestRateRepository")
    async def test_seeds_forwards_for_alpha_fund(
        self, MockRateRepo: MagicMock, MockFwdRepo: MagicMock
    ) -> None:
        app = MagicMock()
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("alpha")])
        app.state.fund_repo = fund_repo

        rate_repo = AsyncMock()
        rate_repo.get_all = AsyncMock(return_value=[])
        rate_repo.upsert = AsyncMock()
        MockRateRepo.return_value = rate_repo

        forward_repo = AsyncMock()
        forward_repo.get_by_portfolio = AsyncMock(return_value=[])
        forward_repo.create = AsyncMock()
        MockFwdRepo.return_value = forward_repo

        session = AsyncMock()

        await seed_dev_data(app, _FakeSF(session))

        # Alpha fund has 4 forwards (2 equity LS + 2 global macro)
        assert forward_repo.create.call_count == 4

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.repositories.FXForwardRepository")
    @patch("app.modules.fx_hedging.repositories.FXInterestRateRepository")
    async def test_skips_non_alpha_beta_for_forwards(
        self, MockRateRepo: MagicMock, MockFwdRepo: MagicMock
    ) -> None:
        app = MagicMock()
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("gamma")])
        app.state.fund_repo = fund_repo

        rate_repo = AsyncMock()
        rate_repo.get_all = AsyncMock(return_value=[])
        rate_repo.upsert = AsyncMock()
        MockRateRepo.return_value = rate_repo

        forward_repo = AsyncMock()
        forward_repo.get_by_portfolio = AsyncMock(return_value=[])
        forward_repo.create = AsyncMock()
        MockFwdRepo.return_value = forward_repo

        session = AsyncMock()

        await seed_dev_data(app, _FakeSF(session))

        forward_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.repositories.FXForwardRepository")
    @patch("app.modules.fx_hedging.repositories.FXInterestRateRepository")
    async def test_skips_forwards_when_already_exist(
        self, MockRateRepo: MagicMock, MockFwdRepo: MagicMock
    ) -> None:
        app = MagicMock()
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("alpha")])
        app.state.fund_repo = fund_repo

        rate_repo = AsyncMock()
        rate_repo.get_all = AsyncMock(return_value=[])
        rate_repo.upsert = AsyncMock()
        MockRateRepo.return_value = rate_repo

        forward_repo = AsyncMock()
        forward_repo.get_by_portfolio = AsyncMock(return_value=[MagicMock()])
        forward_repo.create = AsyncMock()
        MockFwdRepo.return_value = forward_repo

        session = AsyncMock()

        await seed_dev_data(app, _FakeSF(session))

        forward_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.repositories.FXForwardRepository")
    @patch("app.modules.fx_hedging.repositories.FXInterestRateRepository")
    async def test_seeds_forwards_for_beta_fund(
        self, MockRateRepo: MagicMock, MockFwdRepo: MagicMock
    ) -> None:
        app = MagicMock()
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("beta")])
        app.state.fund_repo = fund_repo

        rate_repo = AsyncMock()
        rate_repo.get_all = AsyncMock(return_value=[])
        rate_repo.upsert = AsyncMock()
        MockRateRepo.return_value = rate_repo

        forward_repo = AsyncMock()
        forward_repo.get_by_portfolio = AsyncMock(return_value=[])
        forward_repo.create = AsyncMock()
        MockFwdRepo.return_value = forward_repo

        session = AsyncMock()

        await seed_dev_data(app, _FakeSF(session))

        # Beta fund has 1 forward (stat arb EUR)
        assert forward_repo.create.call_count == 1
