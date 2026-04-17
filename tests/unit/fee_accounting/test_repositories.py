"""Unit tests for fee accounting repositories — verifies SQL queries and
session handling without touching a real database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.fee_accounting.models.fee_accrual import FeeAccrualRecord
from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord
from app.modules.fee_accounting.models.high_water_mark import HighWaterMarkRecord
from app.modules.fee_accounting.repositories.fee_accrual import FeeAccrualRepository
from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
from app.modules.fee_accounting.repositories.high_water_mark import HighWaterMarkRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory():
    """Build a mock TenantSessionFactory whose __call__ yields a mock session."""
    sf = MagicMock()
    mock_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = session_cm
    return sf, mock_session


# ---------------------------------------------------------------------------
# FeeAccrualRepository
# ---------------------------------------------------------------------------


class TestFeeAccrualRepository:
    @pytest.mark.asyncio
    async def test_get_by_portfolio_basic(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        record = MagicMock(spec=FeeAccrualRecord)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [record]
        session.execute.return_value = result_mock

        pid = uuid4()
        result = await repo.get_by_portfolio(pid)

        assert result == [record]
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_portfolio_with_date_filters(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        await repo.get_by_portfolio(
            uuid4(), start=date(2026, 1, 1), end=date(2026, 3, 31)
        )

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_portfolio_with_provided_session(self) -> None:
        sf, _ = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        provided = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        provided.execute.return_value = result_mock

        result = await repo.get_by_portfolio(uuid4(), session=provided)

        assert result == []
        provided.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_by_type(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        record = MagicMock(spec=FeeAccrualRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        session.execute.return_value = result_mock

        result = await repo.get_latest_by_type(uuid4(), "management")

        assert result is record
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_by_type_with_share_class(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        result = await repo.get_latest_by_type(
            uuid4(), "performance", share_class="founders"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        record = MagicMock(spec=FeeAccrualRecord)
        result = await repo.insert(record)

        session.add(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(record)
        assert result is record

    @pytest.mark.asyncio
    async def test_update_status(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeAccrualRepository(sf)

        accrual_id = uuid4()
        await repo.update_status(accrual_id, "crystallized")

        session.execute.assert_called_once()
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# FeeScheduleRepository
# ---------------------------------------------------------------------------


class TestFeeScheduleRepository:
    @pytest.mark.asyncio
    async def test_get_by_fund_slug(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeScheduleRepository(sf)

        record = MagicMock(spec=FeeScheduleRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        session.execute.return_value = result_mock

        result = await repo.get_by_fund_slug("alpha")

        assert result is record
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_fund_slug_with_share_class(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeScheduleRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        result = await repo.get_by_fund_slug("alpha", share_class="founders")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_fund(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeScheduleRepository(sf)

        r1, r2 = MagicMock(spec=FeeScheduleRecord), MagicMock(spec=FeeScheduleRecord)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [r1, r2]
        session.execute.return_value = result_mock

        result = await repo.list_by_fund("alpha")

        assert result == [r1, r2]

    @pytest.mark.asyncio
    async def test_upsert_creates_new(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeScheduleRepository(sf)

        # No existing record
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        session.execute.return_value = existing_result

        record = MagicMock(spec=FeeScheduleRecord)
        record.fund_slug = "alpha"
        record.share_class = "default"

        result = await repo.upsert(record)

        session.add(record)
        session.flush.assert_called()
        session.commit.assert_called()
        assert result is record

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self) -> None:
        sf, session = _make_session_factory()
        repo = FeeScheduleRepository(sf)

        existing_record = MagicMock(spec=FeeScheduleRecord)
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_record
        session.execute.return_value = existing_result

        new_record = MagicMock(spec=FeeScheduleRecord)
        new_record.fund_slug = "alpha"
        new_record.share_class = "default"
        new_record.management_fee_bps = 150
        new_record.performance_fee_pct = Decimal("0.15")
        new_record.hurdle_rate_pct = Decimal("0.06")
        new_record.high_water_mark = True
        new_record.crystallization_frequency = "quarterly"
        new_record.payment_frequency = "quarterly"

        result = await repo.upsert(new_record)

        # Should update the existing record's fields
        assert existing_record.management_fee_bps == 150
        assert existing_record.performance_fee_pct == Decimal("0.15")
        assert existing_record.hurdle_rate_pct == Decimal("0.06")
        assert existing_record.high_water_mark is True
        assert existing_record.crystallization_frequency == "quarterly"
        assert existing_record.payment_frequency == "quarterly"
        session.flush.assert_called()
        session.commit.assert_called()
        assert result is existing_record


# ---------------------------------------------------------------------------
# HighWaterMarkRepository
# ---------------------------------------------------------------------------


class TestHighWaterMarkRepository:
    @pytest.mark.asyncio
    async def test_get_latest(self) -> None:
        sf, session = _make_session_factory()
        repo = HighWaterMarkRepository(sf)

        record = MagicMock(spec=HighWaterMarkRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        session.execute.return_value = result_mock

        result = await repo.get_latest(uuid4())

        assert result is record
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_latest_with_share_class(self) -> None:
        sf, session = _make_session_factory()
        repo = HighWaterMarkRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        result = await repo.get_latest(uuid4(), share_class="founders")

        assert result is None

    @pytest.mark.asyncio
    async def test_upsert(self) -> None:
        sf, session = _make_session_factory()
        repo = HighWaterMarkRepository(sf)

        record = MagicMock(spec=HighWaterMarkRecord)
        result = await repo.upsert(record)

        session.add(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(record)
        assert result is record
