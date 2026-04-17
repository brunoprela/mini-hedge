"""Unit tests for fund_structures repositories."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.fund_structures.repositories.fund_of_funds import FundOfFundsRepository
from app.modules.fund_structures.repositories.master_feeder import MasterFeederRepository
from app.modules.fund_structures.repositories.strategy_book import StrategyBookRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_repo(repo_cls):
    """Create a repo with a mocked session factory."""
    session = _mock_session()
    factory = MagicMock()

    @asynccontextmanager
    async def _fake_factory():
        yield session

    factory.side_effect = _fake_factory
    repo = repo_cls(session_factory=factory)
    return repo, session


def _scalars_result(rows):
    """Build a mock result whose .scalars().all() returns rows."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _scalar_one_or_none_result(value):
    """Build a mock result whose .scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# MasterFeederRepository
# ---------------------------------------------------------------------------


class TestMasterFeederRepository:
    @pytest.mark.asyncio
    async def test_insert_link_adds_and_commits(self) -> None:
        repo, session = _make_repo(MasterFeederRepository)
        record = MagicMock()

        await repo.insert_link(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_link_with_explicit_session(self) -> None:
        repo, _ = _make_repo(MasterFeederRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.insert_link(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_feeders_for_master(self) -> None:
        repo, session = _make_repo(MasterFeederRepository)
        rows = [MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_scalars_result(rows))

        result = await repo.get_feeders_for_master("alpha")

        assert result == rows
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_master_for_feeder_found(self) -> None:
        repo, session = _make_repo(MasterFeederRepository)
        record = MagicMock()
        session.execute = AsyncMock(return_value=_scalar_one_or_none_result(record))

        result = await repo.get_master_for_feeder("feeder-a")

        assert result is record

    @pytest.mark.asyncio
    async def test_get_master_for_feeder_not_found(self) -> None:
        repo, session = _make_repo(MasterFeederRepository)
        session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

        result = await repo.get_master_for_feeder("no-such-feeder")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_allocation(self) -> None:
        repo, session = _make_repo(MasterFeederRepository)
        updated = MagicMock()
        # First execute is the UPDATE, second is the SELECT
        session.execute = AsyncMock(
            side_effect=[MagicMock(), _scalar_one_or_none_result(updated)]
        )

        result = await repo.update_allocation("link-1", Decimal("0.55"))

        assert result is updated
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate(self) -> None:
        repo, session = _make_repo(MasterFeederRepository)

        await repo.deactivate("link-1")

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# StrategyBookRepository
# ---------------------------------------------------------------------------


class TestStrategyBookRepository:
    @pytest.mark.asyncio
    async def test_insert_adds_and_commits(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        record = MagicMock()

        await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_with_explicit_session(self) -> None:
        repo, _ = _make_repo(StrategyBookRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.insert(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        record = MagicMock()
        session.execute = AsyncMock(return_value=_scalar_one_or_none_result(record))

        result = await repo.get_by_id("book-1")

        assert result is record

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

        result = await repo.get_by_id("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_fund(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        rows = [MagicMock(), MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_scalars_result(rows))

        result = await repo.list_by_fund("alpha")

        assert result == rows

    @pytest.mark.asyncio
    async def test_get_children(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        rows = [MagicMock()]
        session.execute = AsyncMock(return_value=_scalars_result(rows))

        result = await repo.get_children("parent-1")

        assert result == rows

    @pytest.mark.asyncio
    async def test_get_tree_delegates_to_list_by_fund(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        rows = [MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_scalars_result(rows))

        result = await repo.get_tree("alpha")

        assert result == rows

    @pytest.mark.asyncio
    async def test_update_with_name(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        updated = MagicMock()
        # First execute is UPDATE, second is SELECT
        session.execute = AsyncMock(
            side_effect=[MagicMock(), _scalar_one_or_none_result(updated)]
        )

        result = await repo.update("book-1", name="New Name")

        assert result is updated
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_with_target_pct(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        updated = MagicMock()
        session.execute = AsyncMock(
            side_effect=[MagicMock(), _scalar_one_or_none_result(updated)]
        )

        result = await repo.update("book-1", target_pct=Decimal("0.75"))

        assert result is updated
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_with_no_changes_skips_update_statement(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        existing = MagicMock()
        # Only the SELECT fires (no UPDATE when no values to change)
        session.execute = AsyncMock(return_value=_scalar_one_or_none_result(existing))

        result = await repo.update("book-1")

        assert result is existing
        # Only one execute call (the SELECT), no commit
        session.execute.assert_awaited_once()
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_not_found(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)
        session.execute = AsyncMock(
            side_effect=[MagicMock(), _scalar_one_or_none_result(None)]
        )

        result = await repo.update("missing", name="X")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_soft_deletes(self) -> None:
        repo, session = _make_repo(StrategyBookRepository)

        await repo.delete("book-1")

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# FundOfFundsRepository
# ---------------------------------------------------------------------------


class TestFundOfFundsRepository:
    @pytest.mark.asyncio
    async def test_insert_holding_adds_and_commits(self) -> None:
        repo, session = _make_repo(FundOfFundsRepository)
        record = MagicMock()

        await repo.insert_holding(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_holding_with_explicit_session(self) -> None:
        repo, _ = _make_repo(FundOfFundsRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.insert_holding(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_holdings(self) -> None:
        repo, session = _make_repo(FundOfFundsRepository)
        rows = [MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_scalars_result(rows))

        result = await repo.list_holdings("fof-alpha")

        assert result == rows

    @pytest.mark.asyncio
    async def test_list_holdings_empty(self) -> None:
        repo, session = _make_repo(FundOfFundsRepository)
        session.execute = AsyncMock(return_value=_scalars_result([]))

        result = await repo.list_holdings("fof-empty")

        assert result == []

    @pytest.mark.asyncio
    async def test_update_nav(self) -> None:
        repo, session = _make_repo(FundOfFundsRepository)

        await repo.update_nav("holding-1", Decimal("123456.78"))

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_holding_soft_deletes(self) -> None:
        repo, session = _make_repo(FundOfFundsRepository)

        await repo.delete_holding("holding-1")

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()
