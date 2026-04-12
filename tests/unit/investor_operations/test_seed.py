"""Unit tests for investor_operations.seed — dev data seeding."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.investor_operations.repositories.fund_terms import FundTermsRepository


def _make_fund(slug: str = "test-fund") -> MagicMock:
    f = MagicMock()
    f.slug = slug
    return f


class _AsyncCM:
    """Async context manager that yields the given value."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        pass


def _make_sf(session: AsyncMock) -> MagicMock:
    """Build a mock TenantSessionFactory."""
    sf = MagicMock()

    @asynccontextmanager
    async def _fund_scope(slug):
        yield

    sf.fund_scope = _fund_scope
    # sf() must return an async context manager
    sf.return_value = _AsyncCM(session)
    return sf


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_seeds_terms_when_none_exist(self) -> None:
        from app.modules.investor_operations.seed import seed_dev_data

        app = MagicMock()
        kyc_service = AsyncMock()
        app.state.kyc_service = kyc_service

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("fund-a")])
        app.state.fund_repo = fund_repo

        session = AsyncMock()

        terms_repo_mock = AsyncMock()
        terms_repo_mock.get_all_active = AsyncMock(return_value=[])

        sf = _make_sf(session)

        with patch.object(FundTermsRepository, "__init__", lambda self, sf: None), \
             patch.object(FundTermsRepository, "get_all_active", terms_repo_mock.get_all_active):
            await seed_dev_data(app, sf)

        kyc_service.upsert_fund_terms.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_seed_when_terms_exist(self) -> None:
        from app.modules.investor_operations.seed import seed_dev_data

        app = MagicMock()
        kyc_service = AsyncMock()
        app.state.kyc_service = kyc_service

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[_make_fund("fund-a")])
        app.state.fund_repo = fund_repo

        session = AsyncMock()

        terms_repo_mock = AsyncMock()
        terms_repo_mock.get_all_active = AsyncMock(return_value=[MagicMock()])

        sf = _make_sf(session)

        with patch.object(FundTermsRepository, "__init__", lambda self, sf: None), \
             patch.object(FundTermsRepository, "get_all_active", terms_repo_mock.get_all_active):
            await seed_dev_data(app, sf)

        kyc_service.upsert_fund_terms.assert_not_called()
