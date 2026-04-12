"""Unit tests for fund_structures.seed."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.fund_structures.seed import seed_dev_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fund(slug: str) -> MagicMock:
    f = MagicMock()
    f.slug = slug
    return f


def _make_app(svc: AsyncMock, fund_repo: AsyncMock) -> MagicMock:
    app = MagicMock()
    app.state.fund_structures_service = svc
    app.state.fund_repo = fund_repo
    return app


def _make_session_factory() -> MagicMock:
    sf = MagicMock()
    # fund_scope returns a sync context manager
    scope_cm = MagicMock()
    scope_cm.__enter__ = MagicMock(return_value=None)
    scope_cm.__exit__ = MagicMock(return_value=False)
    sf.fund_scope.return_value = scope_cm
    # sf() returns an async context manager yielding a session
    session = AsyncMock()
    acm = AsyncMock()
    acm.__aenter__ = AsyncMock(return_value=session)
    acm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = acm
    return sf


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_creates_master_feeder_links_when_all_funds_exist(self) -> None:
        svc = AsyncMock()
        svc.get_feeder_structure = AsyncMock(return_value=[])
        svc.create_master_feeder_link = AsyncMock()
        svc.get_book_tree = AsyncMock(return_value=[])
        svc.create_book = AsyncMock(return_value=MagicMock(id="book-1"))

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(svc, fund_repo)
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        assert svc.create_master_feeder_link.call_count == 2
        calls = svc.create_master_feeder_link.call_args_list
        assert calls[0].args == ("alpha", "beta", Decimal("0.40"))
        assert calls[1].args == ("alpha", "gamma", Decimal("0.25"))

    @pytest.mark.asyncio
    async def test_skips_master_feeder_when_links_exist(self) -> None:
        svc = AsyncMock()
        svc.get_feeder_structure = AsyncMock(return_value=[MagicMock()])
        svc.create_master_feeder_link = AsyncMock()
        svc.get_book_tree = AsyncMock(return_value=[])
        svc.create_book = AsyncMock(return_value=MagicMock(id="book-1"))

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(svc, fund_repo)
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        svc.create_master_feeder_link.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_master_feeder_when_funds_missing(self) -> None:
        svc = AsyncMock()
        svc.get_feeder_structure = AsyncMock(return_value=[])
        svc.create_master_feeder_link = AsyncMock()
        svc.get_book_tree = AsyncMock(return_value=[])
        svc.create_book = AsyncMock(return_value=MagicMock(id="book-1"))

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [_make_fund("alpha")]

        app = _make_app(svc, fund_repo)
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        svc.create_master_feeder_link.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_strategy_books_for_alpha(self) -> None:
        svc = AsyncMock()
        svc.get_feeder_structure = AsyncMock(return_value=[])
        svc.create_master_feeder_link = AsyncMock()
        svc.get_book_tree = AsyncMock(return_value=[])
        # Each create_book returns a mock with an id attribute
        svc.create_book = AsyncMock(return_value=MagicMock(id="book-1"))

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(svc, fund_repo)
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        # 6 books: Total Fund, Equity L/S, Equity Long, Equity Short, Event Driven, Cash & Hedges
        assert svc.create_book.call_count == 6

    @pytest.mark.asyncio
    async def test_skips_books_when_books_exist(self) -> None:
        svc = AsyncMock()
        svc.get_feeder_structure = AsyncMock(return_value=[])
        svc.create_master_feeder_link = AsyncMock()
        svc.get_book_tree = AsyncMock(return_value=[MagicMock()])
        svc.create_book = AsyncMock()

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(svc, fund_repo)
        sf = _make_session_factory()

        await seed_dev_data(app, sf)

        svc.create_book.assert_not_called()

    @pytest.mark.asyncio
    async def test_master_feeder_exception_does_not_propagate(self) -> None:
        svc = AsyncMock()
        svc.get_feeder_structure = AsyncMock(side_effect=Exception("boom"))
        svc.get_book_tree = AsyncMock(return_value=[])
        svc.create_book = AsyncMock(return_value=MagicMock(id="book-1"))

        fund_repo = AsyncMock()
        fund_repo.get_all_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(svc, fund_repo)
        sf = _make_session_factory()

        # Should not raise — exception is caught and logged
        await seed_dev_data(app, sf)
