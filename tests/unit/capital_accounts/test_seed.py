"""Unit tests for capital accounts seed module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.capital_accounts.seed import seed_dev_data


def _make_app(
    *,
    existing_investors: list | None = None,
    active_funds: list | None = None,
    existing_accounts: list | None = None,
) -> MagicMock:
    app = MagicMock()

    investor_repo = AsyncMock()
    investor_repo.get_all_active = AsyncMock(return_value=existing_investors or [])
    investor_repo.insert_batch = AsyncMock()

    capital_transaction_service = AsyncMock()
    capital_transaction_service.process_subscription = AsyncMock()

    app.state.investor_repo = investor_repo
    app.state.capital_transaction_service = capital_transaction_service

    fund_repo = AsyncMock()
    fund_repo.get_all_active = AsyncMock(return_value=active_funds or [])
    app.state.fund_repo = fund_repo

    return app


def _make_fund(slug: str = "test-fund") -> MagicMock:
    fund = MagicMock()
    fund.slug = slug
    return fund


def _make_session_factory(*, existing_accounts: list | None = None) -> MagicMock:
    sf = MagicMock()

    session = AsyncMock()
    # fund_scope returns an async context manager
    fund_scope_cm = AsyncMock()
    fund_scope_cm.__aenter__ = AsyncMock(return_value=None)
    fund_scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope = MagicMock(return_value=fund_scope_cm)

    # sf() returns an async context manager that yields session
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    sf.__call__ = MagicMock(return_value=session_cm)

    return sf


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_seeds_investors_when_none_exist(self) -> None:
        app = _make_app(existing_investors=[], active_funds=[])
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        app.state.investor_repo.insert_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_investor_seed_when_already_exist(self) -> None:
        existing = [MagicMock()]
        app = _make_app(existing_investors=existing, active_funds=[])
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        app.state.investor_repo.insert_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_seeds_subscriptions_for_active_funds(self) -> None:
        fund = _make_fund("alpha-fund")
        app = _make_app(existing_investors=[], active_funds=[fund])
        sf = _make_session_factory()

        # Patch CapitalAccountRepository at the source module
        with patch(
            "app.modules.capital_accounts.repositories.account.CapitalAccountRepository"
        ) as MockRepo:
            mock_account_repo = AsyncMock()
            mock_account_repo.get_latest_by_fund = AsyncMock(return_value=[])
            MockRepo.return_value = mock_account_repo

            await seed_dev_data(app, sf)

        # process_subscription should have been called for each SEED_SUBSCRIPTIONS entry
        assert app.state.capital_transaction_service.process_subscription.call_count > 0

    @pytest.mark.asyncio
    async def test_skips_subscriptions_when_accounts_exist(self) -> None:
        fund = _make_fund("alpha-fund")
        app = _make_app(existing_investors=[], active_funds=[fund])
        sf = _make_session_factory()

        with patch(
            "app.modules.capital_accounts.repositories.account.CapitalAccountRepository"
        ) as MockRepo:
            mock_account_repo = AsyncMock()
            # Return existing accounts so seeding is skipped
            mock_account_repo.get_latest_by_fund = AsyncMock(return_value=[MagicMock()])
            MockRepo.return_value = mock_account_repo

            await seed_dev_data(app, sf)

        app.state.capital_transaction_service.process_subscription.assert_not_called()
