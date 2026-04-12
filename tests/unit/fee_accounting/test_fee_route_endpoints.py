"""Unit tests for fee accounting route endpoint functions (the async handlers)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.modules.fee_accounting.interfaces import AccrualStatus, FeeType
from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord
from app.modules.fee_accounting.routes.fee import (
    FeeScheduleUpdate,
    _schedule_to_response,
    get_fee_schedule,
    get_fee_summary,
    list_accruals,
    list_fee_schedules,
    trigger_crystallization,
    trigger_daily_accrual,
    update_fee_schedule,
)

_PID = UUID("00000000-0000-0000-0000-000000000001")


def _mock_schedule_record(**overrides) -> MagicMock:
    r = MagicMock(spec=FeeScheduleRecord)
    r.fund_slug = overrides.get("fund_slug", "alpha")
    r.share_class = overrides.get("share_class", "default")
    r.management_fee_bps = overrides.get("management_fee_bps", 200)
    r.performance_fee_pct = overrides.get("performance_fee_pct", Decimal("0.20"))
    r.hurdle_rate_pct = overrides.get("hurdle_rate_pct", Decimal("0.05"))
    r.high_water_mark = overrides.get("high_water_mark", True)
    r.crystallization_frequency = overrides.get("crystallization_frequency", "quarterly")
    r.payment_frequency = overrides.get("payment_frequency", "quarterly")
    return r


def _mock_accrual_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = overrides.get("id", "00000000-0000-0000-0000-000000000099")
    r.portfolio_id = overrides.get("portfolio_id", str(_PID))
    r.fee_type = overrides.get("fee_type", FeeType.MANAGEMENT)
    r.accrual_date = overrides.get("accrual_date", date(2026, 3, 31))
    r.nav_basis = overrides.get("nav_basis", Decimal("50000000"))
    r.accrued_amount = overrides.get("accrued_amount", Decimal("5479.45"))
    r.cumulative_amount = overrides.get("cumulative_amount", Decimal("100000"))
    r.status = overrides.get("status", AccrualStatus.ACCRUED)
    r.created_at = overrides.get("created_at", "2026-03-31T00:00:00+00:00")
    return r


# ---------------------------------------------------------------------------
# _schedule_to_response
# ---------------------------------------------------------------------------


class TestScheduleToResponse:
    def test_converts_record_to_response(self) -> None:
        record = _mock_schedule_record()
        resp = _schedule_to_response(record)

        assert resp.fund_slug == "alpha"
        assert resp.share_class == "default"
        assert resp.management_fee_bps == 200
        assert resp.performance_fee_pct == Decimal("0.20")
        assert resp.high_water_mark is True
        assert resp.crystallization_frequency == "quarterly"


# ---------------------------------------------------------------------------
# list_accruals
# ---------------------------------------------------------------------------


class TestListAccruals:
    @pytest.mark.asyncio
    async def test_returns_accrual_responses(self) -> None:
        accrual = _mock_accrual_record()
        fee_service = AsyncMock()
        fee_service.get_accruals = AsyncMock(return_value=[accrual])
        session = AsyncMock()

        result = await list_accruals(
            fund_slug="alpha",
            portfolio_id=_PID,
            start=None,
            end=None,
            fee_service=fee_service,
            session=session,
        )

        assert len(result) == 1
        assert result[0].portfolio_id == _PID
        assert result[0].fee_type == FeeType.MANAGEMENT

    @pytest.mark.asyncio
    async def test_returns_empty_list(self) -> None:
        fee_service = AsyncMock()
        fee_service.get_accruals = AsyncMock(return_value=[])
        session = AsyncMock()

        result = await list_accruals(
            fund_slug="alpha",
            portfolio_id=_PID,
            start=date(2026, 1, 1),
            end=date(2026, 3, 31),
            fee_service=fee_service,
            session=session,
        )

        assert result == []


# ---------------------------------------------------------------------------
# get_fee_schedule
# ---------------------------------------------------------------------------


class TestGetFeeSchedule:
    @pytest.mark.asyncio
    async def test_returns_schedule(self) -> None:
        record = _mock_schedule_record()
        schedule_repo = AsyncMock()
        schedule_repo.get_by_fund_slug = AsyncMock(return_value=record)
        session = AsyncMock()

        result = await get_fee_schedule(
            fund_slug="alpha",
            share_class="default",
            schedule_repo=schedule_repo,
            session=session,
        )

        assert result.fund_slug == "alpha"
        assert result.management_fee_bps == 200

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        schedule_repo = AsyncMock()
        schedule_repo.get_by_fund_slug = AsyncMock(return_value=None)
        session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_fee_schedule(
                fund_slug="alpha",
                share_class="default",
                schedule_repo=schedule_repo,
                session=session,
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_fee_schedules
# ---------------------------------------------------------------------------


class TestListFeeSchedules:
    @pytest.mark.asyncio
    async def test_returns_all_schedules(self) -> None:
        r1 = _mock_schedule_record(share_class="default")
        r2 = _mock_schedule_record(share_class="founders", management_fee_bps=100)
        schedule_repo = AsyncMock()
        schedule_repo.get_all_by_fund = AsyncMock(return_value=[r1, r2])
        session = AsyncMock()

        result = await list_fee_schedules(
            fund_slug="alpha",
            schedule_repo=schedule_repo,
            session=session,
        )

        assert len(result) == 2
        assert result[0].share_class == "default"
        assert result[1].share_class == "founders"


# ---------------------------------------------------------------------------
# update_fee_schedule
# ---------------------------------------------------------------------------


class TestUpdateFeeSchedule:
    @pytest.mark.asyncio
    async def test_upserts_and_returns_response(self) -> None:
        saved = _mock_schedule_record(management_fee_bps=150)
        schedule_repo = AsyncMock()
        schedule_repo.upsert = AsyncMock(return_value=saved)
        session = AsyncMock()

        body = FeeScheduleUpdate(
            share_class="default",
            management_fee_bps=150,
            performance_fee_pct=Decimal("0.15"),
            hurdle_rate_pct=Decimal("0.06"),
            high_water_mark=True,
            crystallization_frequency="quarterly",
            payment_frequency="quarterly",
        )

        result = await update_fee_schedule(
            fund_slug="alpha",
            body=body,
            schedule_repo=schedule_repo,
            session=session,
        )

        assert result.management_fee_bps == 150
        schedule_repo.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# get_fee_summary
# ---------------------------------------------------------------------------


class TestGetFeeSummary:
    @pytest.mark.asyncio
    async def test_returns_summary(self) -> None:
        fee_service = AsyncMock()
        fee_service.get_fee_summary = AsyncMock(
            return_value={"management": Decimal("5000"), "performance": Decimal("12000")}
        )
        session = AsyncMock()

        result = await get_fee_summary(
            fund_slug="alpha",
            portfolio_id=_PID,
            fee_service=fee_service,
            session=session,
        )

        assert result.portfolio_id == _PID
        assert result.totals["management"] == Decimal("5000")


# ---------------------------------------------------------------------------
# trigger_daily_accrual
# ---------------------------------------------------------------------------


class TestTriggerDailyAccrual:
    @pytest.mark.asyncio
    async def test_returns_accrual_responses(self) -> None:
        from app.modules.fee_accounting.routes.fee import AccrualTriggerRequest

        accrual = _mock_accrual_record()
        fee_service = AsyncMock()
        fee_service.accrue_daily_fees = AsyncMock(return_value=[accrual])
        session = AsyncMock()

        body = AccrualTriggerRequest(
            portfolio_id=_PID,
            nav=Decimal("50000000"),
            business_date=date(2026, 3, 31),
        )

        result = await trigger_daily_accrual(
            fund_slug="alpha",
            body=body,
            fee_service=fee_service,
            session=session,
        )

        assert len(result) == 1
        assert result[0].accrued_amount == Decimal("5479.45")


# ---------------------------------------------------------------------------
# trigger_crystallization
# ---------------------------------------------------------------------------


class TestTriggerCrystallization:
    @pytest.mark.asyncio
    async def test_calls_crystallize(self) -> None:
        from app.modules.fee_accounting.routes.fee import CrystallizationTriggerRequest

        fee_service = AsyncMock()
        fee_service.crystallize_fees = AsyncMock()
        session = AsyncMock()

        body = CrystallizationTriggerRequest(
            portfolio_id=_PID,
            business_date=date(2026, 3, 31),
        )

        result = await trigger_crystallization(
            fund_slug="alpha",
            body=body,
            fee_service=fee_service,
            session=session,
        )

        assert result is None
        fee_service.crystallize_fees.assert_called_once_with(
            _PID,
            "alpha",
            date(2026, 3, 31),
            share_class="default",
            session=session,
        )
