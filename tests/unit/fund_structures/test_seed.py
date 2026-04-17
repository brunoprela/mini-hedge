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


def _make_app(fund_repo: AsyncMock) -> MagicMock:
    app = MagicMock()
    app.state.fund_repo = fund_repo
    return app


def _make_session_factory() -> tuple[MagicMock, AsyncMock]:
    """Return (factory, session) where factory yields session via async context manager."""
    sf = MagicMock()
    session = AsyncMock()
    # add / add_all are synchronous in SQLAlchemy — use MagicMock to avoid
    # "coroutine never awaited" warnings.
    session.add = MagicMock()
    session.add_all = MagicMock()

    # sf.fund_scope(slug) returns an async context manager
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm

    # sf() returns an async context manager yielding a session
    acm = AsyncMock()
    acm.__aenter__ = AsyncMock(return_value=session)
    acm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = acm

    return sf, session


def _scalars_result(first_value):
    """Build a mock that mimics result.scalars().first()."""
    scalars = MagicMock()
    scalars.first.return_value = first_value
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_creates_master_feeder_links_when_all_funds_exist(self) -> None:
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(fund_repo)
        sf, session = _make_session_factory()

        # First execute returns no existing link, second returns no existing book
        session.execute = AsyncMock(
            side_effect=[
                _scalars_result(None),  # master-feeder check
                _scalars_result(None),  # strategy book check
            ]
        )

        await seed_dev_data(app, sf)

        # Should have called add_all for master-feeder links
        assert session.add_all.call_count >= 1
        # Should have committed (at least for master-feeder block)
        assert session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_skips_master_feeder_when_links_exist(self) -> None:
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(fund_repo)
        sf, session = _make_session_factory()

        existing_link = MagicMock()
        # First execute finds existing link, second finds no existing book
        session.execute = AsyncMock(
            side_effect=[
                _scalars_result(existing_link),  # master-feeder check — exists
                _scalars_result(None),            # strategy book check
            ]
        )

        await seed_dev_data(app, sf)

        # add_all should only be called for strategy books, not for master-feeder
        # The master-feeder block should be skipped since links exist
        # We check that add_all was NOT called in the master-feeder context
        # by verifying the first add_all call (if any) is for strategy books
        calls = session.add_all.call_args_list
        for call in calls:
            records = call[0][0]
            for record in records:
                # None of the add_all records should be MasterFeederLinkRecord
                assert not hasattr(record, 'master_fund_slug') or not isinstance(record.master_fund_slug, str)

    @pytest.mark.asyncio
    async def test_skips_master_feeder_when_funds_missing(self) -> None:
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [_make_fund("alpha")]

        app = _make_app(fund_repo)
        sf, session = _make_session_factory()

        # Only strategy book query runs (master-feeder block is skipped entirely)
        session.execute = AsyncMock(
            side_effect=[
                _scalars_result(None),  # strategy book check
            ]
        )

        await seed_dev_data(app, sf)

        # fund_scope should only be called for strategy books (alpha), not master-feeder
        # since beta and gamma are missing
        assert sf.fund_scope.call_count == 1

    @pytest.mark.asyncio
    async def test_creates_strategy_books_for_alpha(self) -> None:
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(fund_repo)
        sf, session = _make_session_factory()

        # Both checks return nothing — seed everything
        session.execute = AsyncMock(
            side_effect=[
                _scalars_result(None),  # master-feeder check
                _scalars_result(None),  # strategy book check
            ]
        )

        await seed_dev_data(app, sf)

        # Should have called session.add for root and eq_book (flushed individually)
        assert session.add.call_count >= 2
        # Should have called session.flush for root and eq_book
        assert session.flush.call_count >= 2

    @pytest.mark.asyncio
    async def test_skips_books_when_books_exist(self) -> None:
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(fund_repo)
        sf, session = _make_session_factory()

        existing_book = MagicMock()
        # First check: no existing links, second check: existing books
        session.execute = AsyncMock(
            side_effect=[
                _scalars_result(None),           # master-feeder check
                _scalars_result(existing_book),  # strategy book check — exists
            ]
        )

        await seed_dev_data(app, sf)

        # add should not be called for strategy books since they already exist
        # add_all is called once for master-feeder links
        # session.add should not be called (no root/eq_book creation)
        # The master-feeder block uses add_all, strategy books use add + add_all
        # Since books exist, the strategy book add/flush should not happen
        assert session.flush.call_count == 0

    @pytest.mark.asyncio
    async def test_master_feeder_exception_does_not_propagate(self) -> None:
        fund_repo = AsyncMock()
        fund_repo.list_active.return_value = [
            _make_fund("alpha"),
            _make_fund("beta"),
            _make_fund("gamma"),
        ]

        app = _make_app(fund_repo)
        sf, session = _make_session_factory()

        # Make the session raise on execute (simulating DB error in master-feeder block)
        # But we need the strategy book block to work too
        call_count = 0

        async def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("boom")
            return _scalars_result(None)

        session.execute = AsyncMock(side_effect=execute_side_effect)

        # Should not raise — IntegrityError is caught, other exceptions
        # may propagate but the test verifies the general pattern
        # The seed catches IntegrityError specifically, but let's test with that
        from sqlalchemy.exc import IntegrityError

        call_count = 0

        async def execute_integrity_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise IntegrityError("boom", params=None, orig=Exception("boom"))
            return _scalars_result(None)

        session.execute = AsyncMock(side_effect=execute_integrity_error)

        # Should not raise
        await seed_dev_data(app, sf)
