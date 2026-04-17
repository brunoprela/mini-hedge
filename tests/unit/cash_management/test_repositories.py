"""Unit tests for cash management repositories — verifies SQL queries and
session handling without touching a real database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.cash_management.models.cash_balance import CashBalanceRecord
from app.modules.cash_management.models.cash_journal import CashJournalRecord
from app.modules.cash_management.models.cash_projection import CashProjectionRecord
from app.modules.cash_management.models.cash_settlement import CashSettlementRecord
from app.modules.cash_management.models.scheduled_flow import ScheduledFlowRecord
from app.modules.cash_management.repositories.cash_balance import CashBalanceRepository
from app.modules.cash_management.repositories.cash_journal import CashJournalRepository
from app.modules.cash_management.repositories.cash_projection import CashProjectionRepository
from app.modules.cash_management.repositories.scheduled_flow import ScheduledFlowRepository
from app.modules.cash_management.repositories.settlement import SettlementRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory():
    """Build a mock TenantSessionFactory whose __call__ yields a mock session."""
    sf = MagicMock()
    mock_session = AsyncMock()
    # Make the session factory work as async context manager
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = session_cm
    return sf, mock_session


# ---------------------------------------------------------------------------
# CashBalanceRepository
# ---------------------------------------------------------------------------


class TestCashBalanceRepository:
    async def test_get_by_portfolio(self):
        sf, mock_session = _make_session_factory()
        repo = CashBalanceRepository(sf)

        record = MagicMock(spec=CashBalanceRecord)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [record]
        mock_session.execute.return_value = result_mock

        pid = uuid4()
        result = await repo.get_by_portfolio(pid)

        assert result == [record]
        mock_session.execute.assert_called_once()

    async def test_get_by_portfolio_with_session(self):
        sf, _ = _make_session_factory()
        repo = CashBalanceRepository(sf)

        provided_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        provided_session.execute.return_value = result_mock

        result = await repo.get_by_portfolio(uuid4(), session=provided_session)
        assert result == []
        provided_session.execute.assert_called_once()

    async def test_get_by_portfolio_currency(self):
        sf, mock_session = _make_session_factory()
        repo = CashBalanceRepository(sf)

        record = MagicMock(spec=CashBalanceRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_portfolio_currency(uuid4(), "USD")
        assert result is record

    async def test_get_by_portfolio_currency_returns_none(self):
        sf, mock_session = _make_session_factory()
        repo = CashBalanceRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_portfolio_currency(uuid4(), "JPY")
        assert result is None

    async def test_upsert_creates_new(self):
        sf, mock_session = _make_session_factory()
        repo = CashBalanceRepository(sf)

        # No existing row
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = existing_result

        record = CashBalanceRecord(
            portfolio_id=str(uuid4()),
            currency="USD",
            available_balance=Decimal("1000"),
            pending_inflows=Decimal("0"),
            pending_outflows=Decimal("0"),
        )
        await repo.upsert(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_called_once()

    async def test_upsert_updates_existing(self):
        sf, mock_session = _make_session_factory()
        repo = CashBalanceRepository(sf)

        existing_row = MagicMock()
        existing_row.id = "existing-id"
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_row

        # First call returns existing, second call (update) returns something
        mock_session.execute.side_effect = [existing_result, MagicMock()]

        record = CashBalanceRecord(
            portfolio_id=str(uuid4()),
            currency="USD",
            available_balance=Decimal("2000"),
            pending_inflows=Decimal("100"),
            pending_outflows=Decimal("50"),
        )
        await repo.upsert(record)

        # Should have called execute twice (select + update) and commit
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# CashJournalRepository
# ---------------------------------------------------------------------------


class TestCashJournalRepository:
    async def test_insert(self):
        sf, mock_session = _make_session_factory()
        repo = CashJournalRepository(sf)

        record = MagicMock(spec=CashJournalRecord)
        await repo.insert(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_called_once()

    async def test_get_by_portfolio(self):
        sf, mock_session = _make_session_factory()
        repo = CashJournalRepository(sf)

        records = [MagicMock(spec=CashJournalRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_portfolio(uuid4(), limit=50)
        assert result == records


# ---------------------------------------------------------------------------
# CashProjectionRepository
# ---------------------------------------------------------------------------


class TestCashProjectionRepository:
    async def test_insert(self):
        sf, mock_session = _make_session_factory()
        repo = CashProjectionRepository(sf)

        record = MagicMock(spec=CashProjectionRecord)
        await repo.insert(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_called_once()

    async def test_get_latest(self):
        sf, mock_session = _make_session_factory()
        repo = CashProjectionRepository(sf)

        record = MagicMock(spec=CashProjectionRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result_mock

        result = await repo.get_latest(uuid4())
        assert result is record

    async def test_get_latest_none(self):
        sf, mock_session = _make_session_factory()
        repo = CashProjectionRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        result = await repo.get_latest(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# ScheduledFlowRepository
# ---------------------------------------------------------------------------


class TestScheduledFlowRepository:
    async def test_insert(self):
        sf, mock_session = _make_session_factory()
        repo = ScheduledFlowRepository(sf)

        record = MagicMock(spec=ScheduledFlowRecord)
        await repo.insert(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_called_once()

    async def test_get_by_portfolio(self):
        sf, mock_session = _make_session_factory()
        repo = ScheduledFlowRepository(sf)

        records = [MagicMock(spec=ScheduledFlowRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_portfolio(uuid4(), date(2024, 1, 1), date(2024, 12, 31))
        assert result == records


# ---------------------------------------------------------------------------
# SettlementRepository
# ---------------------------------------------------------------------------


class TestSettlementRepository:
    async def test_insert(self):
        sf, mock_session = _make_session_factory()
        repo = SettlementRepository(sf)

        record = MagicMock(spec=CashSettlementRecord)
        await repo.insert(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_called_once()

    async def test_get_pending(self):
        sf, mock_session = _make_session_factory()
        repo = SettlementRepository(sf)

        records = [MagicMock(spec=CashSettlementRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_pending(uuid4())
        assert result == records

    async def test_get_by_date_range(self):
        sf, mock_session = _make_session_factory()
        repo = SettlementRepository(sf)

        records = [MagicMock(spec=CashSettlementRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_date_range(uuid4(), date(2024, 1, 1), date(2024, 1, 31))
        assert result == records

    async def test_settle(self):
        sf, mock_session = _make_session_factory()
        repo = SettlementRepository(sf)

        await repo.settle("settlement-123")

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_get_due_settlements(self):
        sf, mock_session = _make_session_factory()
        repo = SettlementRepository(sf)

        records = [MagicMock(spec=CashSettlementRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_due_settlements(date(2024, 6, 15))
        assert result == records
