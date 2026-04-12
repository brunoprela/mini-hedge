"""Unit tests for capital accounts repositories — mocked DB sessions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.capital_accounts.models.capital_account import CapitalAccountRecord
from app.modules.capital_accounts.models.capital_transaction import CapitalTransactionRecord
from app.modules.capital_accounts.repositories.account import CapitalAccountRepository
from app.modules.capital_accounts.repositories.investor import InvestorRepository
from app.modules.capital_accounts.repositories.transaction import CapitalTransactionRepository
from app.modules.platform.models.investor import InvestorRecord


def _make_session_factory() -> MagicMock:
    sf = MagicMock()
    return sf


def _make_session(*, scalars_result: list | None = None, scalar_one_or_none: object = None) -> AsyncMock:
    """Create a mock session that works with the BaseRepository._session context manager."""
    session = AsyncMock()
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_result or []
    result.scalars.return_value = scalars_mock
    result.scalar_one_or_none.return_value = scalar_one_or_none
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ------------------------------------------------------------------
# CapitalAccountRepository
# ------------------------------------------------------------------


class TestCapitalAccountRepository:
    @pytest.mark.asyncio
    async def test_get_latest_by_fund(self) -> None:
        acct = MagicMock(spec=CapitalAccountRecord)
        session = _make_session(scalars_result=[acct])
        sf = _make_session_factory()
        repo = CapitalAccountRepository(sf)

        result = await repo.get_latest_by_fund(session=session)

        assert result == [acct]
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_investor_no_filters(self) -> None:
        acct = MagicMock(spec=CapitalAccountRecord)
        session = _make_session(scalars_result=[acct])
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_by_investor("inv-1", session=session)

        assert result == [acct]

    @pytest.mark.asyncio
    async def test_get_by_investor_with_date_filters(self) -> None:
        session = _make_session(scalars_result=[])
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_by_investor(
            "inv-1",
            from_date=date(2026, 1, 1),
            to_date=date(2026, 3, 31),
            session=session,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_latest_for_investor(self) -> None:
        acct = MagicMock(spec=CapitalAccountRecord)
        session = _make_session(scalar_one_or_none=acct)
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_latest_for_investor("inv-1", session=session)

        assert result is acct

    @pytest.mark.asyncio
    async def test_get_latest_for_investor_with_share_class(self) -> None:
        session = _make_session(scalar_one_or_none=None)
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_latest_for_investor(
            "inv-1",
            share_class="institutional",
            session=session,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_for_investor_by_class(self) -> None:
        acct = MagicMock(spec=CapitalAccountRecord)
        session = _make_session(scalars_result=[acct])
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_latest_for_investor_by_class("inv-1", session=session)

        assert result == [acct]

    @pytest.mark.asyncio
    async def test_get_latest_by_share_class(self) -> None:
        acct = MagicMock(spec=CapitalAccountRecord)
        session = _make_session(scalars_result=[acct])
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_latest_by_share_class("default", session=session)

        assert result == [acct]

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        record = MagicMock(spec=CapitalAccountRecord)
        session = _make_session()
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(record)
        assert result is record

    @pytest.mark.asyncio
    async def test_get_total_shares_with_accounts(self) -> None:
        acct1 = MagicMock(spec=CapitalAccountRecord)
        acct1.shares_held = Decimal("5000")
        acct2 = MagicMock(spec=CapitalAccountRecord)
        acct2.shares_held = Decimal("3000")
        session = _make_session(scalars_result=[acct1, acct2])
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_total_shares(session=session)

        assert result == Decimal("8000")

    @pytest.mark.asyncio
    async def test_get_total_shares_empty(self) -> None:
        session = _make_session(scalars_result=[])
        repo = CapitalAccountRepository(_make_session_factory())

        result = await repo.get_total_shares(session=session)

        assert result == Decimal("0")


# ------------------------------------------------------------------
# InvestorRepository
# ------------------------------------------------------------------


class TestInvestorRepository:
    @pytest.mark.asyncio
    async def test_get_all_active(self) -> None:
        inv = MagicMock(spec=InvestorRecord)
        session = _make_session(scalars_result=[inv])
        repo = InvestorRepository(_make_session_factory())

        result = await repo.get_all_active(session=session)

        assert result == [inv]

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        inv = MagicMock(spec=InvestorRecord)
        session = _make_session(scalar_one_or_none=inv)
        repo = InvestorRepository(_make_session_factory())

        result = await repo.get_by_id("inv-1", session=session)

        assert result is inv

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _make_session(scalar_one_or_none=None)
        repo = InvestorRepository(_make_session_factory())

        result = await repo.get_by_id("nonexistent", session=session)

        assert result is None

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        record = MagicMock(spec=InvestorRecord)
        session = _make_session()
        repo = InvestorRepository(_make_session_factory())

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_found(self) -> None:
        inv = MagicMock(spec=InvestorRecord)
        inv.name = "Old Name"
        session = _make_session(scalar_one_or_none=inv)
        repo = InvestorRepository(_make_session_factory())

        result = await repo.update("inv-1", name="New Name", session=session)

        assert result is inv
        assert inv.name == "New Name"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self) -> None:
        session = _make_session(scalar_one_or_none=None)
        repo = InvestorRepository(_make_session_factory())

        result = await repo.update("nonexistent", name="Test", session=session)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self) -> None:
        inv = MagicMock(spec=InvestorRecord)
        session = _make_session(scalar_one_or_none=inv)
        repo = InvestorRepository(_make_session_factory())

        result = await repo.update(
            "inv-1",
            name="Updated",
            entity_type="individual",
            tax_jurisdiction="UK",
            contact_email="new@fund.com",
            is_active=False,
            session=session,
        )

        assert inv.name == "Updated"
        assert inv.entity_type == "individual"
        assert inv.tax_jurisdiction == "UK"
        assert inv.contact_email == "new@fund.com"
        assert inv.is_active is False

    @pytest.mark.asyncio
    async def test_insert_batch(self) -> None:
        records = [MagicMock(spec=InvestorRecord), MagicMock(spec=InvestorRecord)]
        session = _make_session()
        repo = InvestorRepository(_make_session_factory())

        await repo.insert_batch(records, session=session)

        session.add_all.assert_called_once_with(records)
        session.flush.assert_called_once()
        session.commit.assert_called_once()


# ------------------------------------------------------------------
# CapitalTransactionRepository
# ------------------------------------------------------------------


class TestCapitalTransactionRepository:
    @pytest.mark.asyncio
    async def test_get_by_account(self) -> None:
        txn = MagicMock(spec=CapitalTransactionRecord)
        session = _make_session(scalars_result=[txn])
        repo = CapitalTransactionRepository(_make_session_factory())

        result = await repo.get_by_account("acct-1", session=session)

        assert result == [txn]

    @pytest.mark.asyncio
    async def test_get_by_investor_no_filters(self) -> None:
        txn = MagicMock(spec=CapitalTransactionRecord)
        session = _make_session(scalars_result=[txn])
        repo = CapitalTransactionRepository(_make_session_factory())

        result = await repo.get_by_investor("inv-1", session=session)

        assert result == [txn]

    @pytest.mark.asyncio
    async def test_get_by_investor_with_date_filters(self) -> None:
        session = _make_session(scalars_result=[])
        repo = CapitalTransactionRepository(_make_session_factory())

        result = await repo.get_by_investor(
            "inv-1",
            from_date=date(2026, 1, 1),
            to_date=date(2026, 3, 31),
            session=session,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        record = MagicMock(spec=CapitalTransactionRecord)
        session = _make_session()
        repo = CapitalTransactionRepository(_make_session_factory())

        result = await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(record)
        assert result is record
