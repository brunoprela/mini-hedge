"""Unit tests for regulatory seed module."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_fund(slug: str = "alpha", name: str = "Alpha Fund") -> MagicMock:
    f = MagicMock()
    f.slug = slug
    f.name = name
    return f


def _make_app(svc: AsyncMock, fund_repo: AsyncMock) -> MagicMock:
    app = MagicMock()
    app.state.regulatory_service = svc
    app.state.fund_repo = fund_repo
    return app


def _make_sf() -> MagicMock:
    """Build a mock TenantSessionFactory that supports async-with patterns."""
    mock_session = AsyncMock()

    @asynccontextmanager
    async def _fund_scope(slug: str):
        yield

    @asynccontextmanager
    async def _call():
        yield mock_session

    sf = MagicMock()
    sf.fund_scope = _fund_scope
    sf.side_effect = lambda: _call()
    # Make sf() return an async context manager
    sf.__call__ = lambda self_: _call()
    return sf


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_seeds_filings_for_active_funds(self) -> None:
        from app.modules.regulatory.seed import seed_dev_data

        svc = AsyncMock()
        svc.list_filings = AsyncMock(return_value=[])
        svc.generate_form_pf = AsyncMock()
        svc.generate_performance_letter = AsyncMock()

        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[_make_fund()])

        app = _make_app(svc, fund_repo)
        sf = _make_sf()

        await seed_dev_data(app, sf)

        svc.generate_form_pf.assert_called_once()
        svc.generate_performance_letter.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_fund_with_existing_filings(self) -> None:
        from app.modules.regulatory.seed import seed_dev_data

        svc = AsyncMock()
        svc.list_filings = AsyncMock(return_value=[{"id": "existing"}])
        svc.generate_form_pf = AsyncMock()
        svc.generate_performance_letter = AsyncMock()

        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[_make_fund()])

        app = _make_app(svc, fund_repo)
        sf = _make_sf()

        await seed_dev_data(app, sf)

        svc.generate_form_pf.assert_not_called()
        svc.generate_performance_letter.assert_not_called()

    @pytest.mark.asyncio
    async def test_seeds_nothing_when_no_active_funds(self) -> None:
        from app.modules.regulatory.seed import seed_dev_data

        svc = AsyncMock()
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[])

        app = _make_app(svc, fund_repo)
        sf = _make_sf()

        await seed_dev_data(app, sf)

        svc.list_filings.assert_not_called()
