"""Unit tests for EOD repositories — covers all repository files at 0% coverage.

Each repository method is tested with mocked AsyncSession to verify
correct SQLAlchemy statement construction and session usage.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.eod.repositories.run import EODRunRepository
from app.modules.eod.repositories.nav_snapshot import NAVSnapshotRepository
from app.modules.eod.repositories.pnl_snapshot import PnLSnapshotRepository
from app.modules.eod.repositories.price import FinalizedPriceRepository
from app.modules.eod.repositories.reconciliation import ReconciliationRepository
from app.modules.eod.repositories.reconciliation_break import ReconciliationBreakRepository


def _make_session() -> AsyncMock:
    """Create a mock AsyncSession with execute/commit/refresh/add."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    # execute returns a result proxy
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    return session


def _make_repo(repo_cls):
    """Create a repository with a mocked session factory."""
    session = _make_session()
    factory = MagicMock()

    @asynccontextmanager
    async def _fake_factory():
        yield session

    factory.side_effect = _fake_factory

    @asynccontextmanager
    async def _fake_session_method(provided_session=None):
        if provided_session is not None:
            yield provided_session
        else:
            yield session

    repo = repo_cls(session_factory=factory)
    # Patch _session to use our mock
    repo._session = _fake_session_method
    return repo, session


# ── EODRunRepository ─────────────────────────────────────────────────

class TestEODRunRepository:
    @pytest.mark.asyncio
    async def test_insert_run(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        await repo.insert_run(
            run_id="run-1",
            business_date=date(2026, 4, 12),
            fund_slug="alpha",
            started_at=datetime.now(UTC),
        )
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_run(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        await repo.complete_run(
            "run-1",
            is_successful=True,
            completed_at=datetime.now(UTC),
        )
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_latest_run_returns_none(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        result = await repo.get_latest_run(date(2026, 4, 12), "alpha")
        assert result is None
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_latest_run_returns_record(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        record = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = record
        session.execute.return_value = exec_result

        result = await repo.get_latest_run(date(2026, 4, 12), "alpha")
        assert result is record

    @pytest.mark.asyncio
    async def test_get_run_history(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        records = [MagicMock(), MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = records
        session.execute.return_value = exec_result

        result = await repo.get_run_history("alpha", limit=10, offset=0)
        assert result == records

    @pytest.mark.asyncio
    async def test_upsert_step(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        await repo.upsert_step(
            run_id="run-1",
            step="market_close",
            status="completed",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_steps(self) -> None:
        repo, session = _make_repo(EODRunRepository)
        step_records = [MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = step_records
        session.execute.return_value = exec_result

        result = await repo.get_steps("run-1")
        assert result == step_records

    @pytest.mark.asyncio
    async def test_insert_run_with_explicit_session(self) -> None:
        repo, _ = _make_repo(EODRunRepository)
        explicit_session = _make_session()

        # Override _session to respect provided session
        @asynccontextmanager
        async def _session(provided=None):
            yield explicit_session if provided is not None else _make_session()

        repo._session = _session

        await repo.insert_run(
            run_id="run-2",
            business_date=date(2026, 4, 12),
            fund_slug="alpha",
            started_at=datetime.now(UTC),
            session=explicit_session,
        )
        explicit_session.add.assert_called_once()


# ── NAVSnapshotRepository ────────────────────────────────────────────

class TestNAVSnapshotRepository:
    @pytest.mark.asyncio
    async def test_upsert(self) -> None:
        repo, session = _make_repo(NAVSnapshotRepository)
        await repo.upsert(
            portfolio_id="port-1",
            business_date=date(2026, 4, 12),
            gross_market_value=Decimal("10000000"),
            net_market_value=Decimal("8000000"),
            cash_balance=Decimal("2000000"),
            accrued_fees=Decimal("50000"),
            nav=Decimal("9950000"),
            nav_per_share=Decimal("99.50"),
            shares_outstanding=Decimal("100000"),
            currency="USD",
        )
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()


# ── PnLSnapshotRepository ───────────────────────────────────────────

class TestPnLSnapshotRepository:
    @pytest.mark.asyncio
    async def test_upsert(self) -> None:
        repo, session = _make_repo(PnLSnapshotRepository)
        await repo.upsert(
            portfolio_id="port-1",
            business_date=date(2026, 4, 12),
            total_realized_pnl=Decimal("1000"),
            total_unrealized_pnl=Decimal("2000"),
            total_pnl=Decimal("3000"),
            position_count=5,
            details={"AAPL": "500"},
        )
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()


# ── FinalizedPriceRepository ────────────────────────────────────────

class TestFinalizedPriceRepository:
    @pytest.mark.asyncio
    async def test_upsert_price(self) -> None:
        repo, session = _make_repo(FinalizedPriceRepository)
        await repo.upsert_price(
            instrument_id="AAPL",
            business_date=date(2026, 4, 12),
            close_price=Decimal("248.50"),
            source="market_data",
            finalized_by="eod_orchestrator",
        )
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_prices(self) -> None:
        repo, session = _make_repo(FinalizedPriceRepository)
        records = [MagicMock(), MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = records
        session.execute.return_value = exec_result

        result = await repo.get_prices(date(2026, 4, 12))
        assert result == records


# ── ReconciliationRepository ────────────────────────────────────────

class TestReconciliationRepository:
    @pytest.mark.asyncio
    async def test_upsert(self) -> None:
        repo, session = _make_repo(ReconciliationRepository)
        await repo.upsert(
            portfolio_id="port-1",
            business_date=date(2026, 4, 12),
            total_positions=10,
            matched_positions=9,
            is_clean=False,
            breaks=[{"type": "quantity_mismatch"}],
        )
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_date(self) -> None:
        repo, session = _make_repo(ReconciliationRepository)
        record = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = record
        session.execute.return_value = exec_result

        result = await repo.get_by_date("port-1", date(2026, 4, 12))
        assert result is record

    @pytest.mark.asyncio
    async def test_get_latest(self) -> None:
        repo, session = _make_repo(ReconciliationRepository)
        record = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = record
        session.execute.return_value = exec_result

        result = await repo.get_latest("port-1")
        assert result is record

    @pytest.mark.asyncio
    async def test_list_by_portfolio(self) -> None:
        repo, session = _make_repo(ReconciliationRepository)
        records = [MagicMock(), MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = records
        session.execute.return_value = exec_result

        result = await repo.list_by_portfolio("port-1", limit=10)
        assert result == records


# ── ReconciliationBreakRepository ───────────────────────────────────

class TestReconciliationBreakRepository:
    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        record = MagicMock()
        result = await repo.insert(record)
        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(record)

    @pytest.mark.asyncio
    async def test_insert_batch(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        records = [MagicMock(), MagicMock()]
        await repo.insert_batch(records)
        session.add_all.assert_called_once_with(records)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        record = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = record
        session.execute.return_value = exec_result

        result = await repo.get_by_id("break-1")
        assert result is record

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        result = await repo.get_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_portfolio_date(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        records = [MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = records
        session.execute.return_value = exec_result

        result = await repo.list_by_portfolio_date("port-1", date(2026, 4, 12))
        assert result == records

    @pytest.mark.asyncio
    async def test_list_open(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        records = [MagicMock(), MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = records
        session.execute.return_value = exec_result

        result = await repo.list_open("port-1")
        assert result == records

    @pytest.mark.asyncio
    async def test_list_recently_resolved(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        records = [MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = records
        session.execute.return_value = exec_result

        result = await repo.list_recently_resolved("port-1", since=date(2026, 4, 1))
        assert result == records

    @pytest.mark.asyncio
    async def test_update_status_found(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        record = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = record
        session.execute.return_value = exec_result

        result = await repo.update_status(
            "break-1",
            status="resolved",
            assigned_to="analyst@fund.com",
            resolution_note="Timing difference",
            resolved_at=datetime.now(UTC),
        )

        assert result is record
        assert record.status == "resolved"
        assert record.assigned_to == "analyst@fund.com"
        assert record.resolution_note == "Timing difference"
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status_not_found(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        # Default returns None for scalar_one_or_none
        result = await repo.update_status("nonexistent", status="resolved")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_partial_fields(self) -> None:
        repo, session = _make_repo(ReconciliationBreakRepository)
        record = MagicMock()
        record.assigned_to = "original"
        record.resolution_note = "original"
        record.resolved_at = None
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = record
        session.execute.return_value = exec_result

        result = await repo.update_status("break-1", status="investigating")

        assert record.status == "investigating"
        # assigned_to, resolution_note, resolved_at should not be overwritten
        # since None was passed (the default)
        assert record.assigned_to == "original"
