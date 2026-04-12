"""Unit tests for FeeAccountingService — accrual, crystallization, queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.fee_accounting.interfaces import AccrualStatus, FeeType
from app.modules.fee_accounting.models.fee_accrual import FeeAccrualRecord
from app.modules.fee_accounting.services.fee import FeeAccountingService

_PORTFOLIO = UUID("00000000-0000-0000-0000-000000000001")
_FUND = "alpha"


def _make_schedule(
    mgmt_bps: int = 200,
    perf_pct: Decimal = Decimal("0.20"),
    hurdle: Decimal = Decimal("0.05"),
    crystallization: str = "quarterly",
) -> MagicMock:
    s = MagicMock()
    s.management_fee_bps = mgmt_bps
    s.performance_fee_pct = perf_pct
    s.hurdle_rate_pct = hurdle
    s.crystallization_frequency = crystallization
    return s


def _make_accrual(
    *,
    fee_type: str = FeeType.MANAGEMENT,
    accrued: Decimal = Decimal("100.00"),
    cumulative: Decimal = Decimal("1000.00"),
    share_class: str = "default",
    status: str = AccrualStatus.ACCRUED,
    nav_basis: Decimal = Decimal("50000000"),
    accrual_date: date = date(2026, 3, 30),
) -> MagicMock:
    a = MagicMock(spec=FeeAccrualRecord)
    a.id = "00000000-0000-0000-0000-000000000099"
    a.portfolio_id = str(_PORTFOLIO)
    a.share_class = share_class
    a.fee_type = fee_type
    a.accrual_date = accrual_date
    a.nav_basis = nav_basis
    a.accrued_amount = accrued
    a.cumulative_amount = cumulative
    a.status = status
    return a


def _make_hwm(
    hwm_nav: Decimal = Decimal("48000000"),
    peak_nav: Decimal = Decimal("50000000"),
    hwm_date: date = date(2026, 1, 1),
) -> MagicMock:
    h = MagicMock()
    h.hwm_nav = hwm_nav
    h.peak_nav = peak_nav
    h.hwm_date = hwm_date
    return h


def _stamp(record, **_kw):
    return record


def _make_service(
    *,
    schedule: MagicMock | None = None,
    latest_mgmt: MagicMock | None = None,
    latest_perf: MagicMock | None = None,
    hwm: MagicMock | None = None,
    accruals: list | None = None,
    event_bus: AsyncMock | None = None,
) -> FeeAccountingService:
    sf = MagicMock()
    schedule_repo = AsyncMock()
    schedule_repo.get_by_fund_slug = AsyncMock(return_value=schedule)

    accrual_repo = AsyncMock()
    accrual_repo.insert = AsyncMock(side_effect=_stamp)
    accrual_repo.get_by_portfolio = AsyncMock(return_value=accruals or [])
    accrual_repo.update_status = AsyncMock()

    def _get_latest(pid, fee_type, **kw):
        if fee_type == FeeType.MANAGEMENT:
            return latest_mgmt
        return latest_perf

    accrual_repo.get_latest_by_type = AsyncMock(side_effect=_get_latest)

    hwm_repo = AsyncMock()
    hwm_repo.get_latest = AsyncMock(return_value=hwm)
    hwm_repo.upsert = AsyncMock()

    return FeeAccountingService(
        session_factory=sf,
        schedule_repo=schedule_repo,
        accrual_repo=accrual_repo,
        hwm_repo=hwm_repo,
        event_bus=event_bus,
    )


# ------------------------------------------------------------------
# accrue_daily_fees
# ------------------------------------------------------------------


class TestAccrueDailyFees:
    @pytest.mark.asyncio
    async def test_accrues_management_fee(self) -> None:
        schedule = _make_schedule(mgmt_bps=200)
        svc = _make_service(schedule=schedule)

        result = await svc.accrue_daily_fees(
            _PORTFOLIO, _FUND, Decimal("50000000"), date(2026, 3, 31)
        )

        # Should have at least 1 accrual (management)
        assert len(result) >= 1
        mgmt = [r for r in result if r.fee_type == FeeType.MANAGEMENT]
        assert len(mgmt) == 1
        assert mgmt[0].accrued_amount > Decimal("0")

    @pytest.mark.asyncio
    async def test_accrues_performance_fee_above_hwm(self) -> None:
        schedule = _make_schedule(perf_pct=Decimal("0.20"), hurdle=Decimal("0"))
        hwm = _make_hwm(hwm_nav=Decimal("48000000"), hwm_date=date(2026, 1, 1))
        svc = _make_service(schedule=schedule, hwm=hwm)

        result = await svc.accrue_daily_fees(
            _PORTFOLIO, _FUND, Decimal("50000000"), date(2026, 3, 31)
        )

        perf = [r for r in result if r.fee_type == FeeType.PERFORMANCE]
        assert len(perf) == 1
        assert perf[0].accrued_amount > Decimal("0")

    @pytest.mark.asyncio
    async def test_no_performance_fee_below_hwm(self) -> None:
        schedule = _make_schedule(perf_pct=Decimal("0.20"), hurdle=Decimal("0"))
        hwm = _make_hwm(hwm_nav=Decimal("55000000"), hwm_date=date(2026, 1, 1))
        svc = _make_service(schedule=schedule, hwm=hwm)

        result = await svc.accrue_daily_fees(
            _PORTFOLIO, _FUND, Decimal("50000000"), date(2026, 3, 31)
        )

        perf = [r for r in result if r.fee_type == FeeType.PERFORMANCE]
        assert len(perf) == 0

    @pytest.mark.asyncio
    async def test_cumulative_adds_to_previous(self) -> None:
        schedule = _make_schedule(mgmt_bps=200)
        prev = _make_accrual(cumulative=Decimal("5000.00"))
        svc = _make_service(schedule=schedule, latest_mgmt=prev)

        result = await svc.accrue_daily_fees(
            _PORTFOLIO, _FUND, Decimal("50000000"), date(2026, 3, 31)
        )

        mgmt = [r for r in result if r.fee_type == FeeType.MANAGEMENT][0]
        assert mgmt.cumulative_amount > Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_returns_empty_without_schedule(self) -> None:
        svc = _make_service(schedule=None)

        result = await svc.accrue_daily_fees(
            _PORTFOLIO, _FUND, Decimal("50000000"), date(2026, 3, 31)
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_persists_accrual_records(self) -> None:
        schedule = _make_schedule()
        svc = _make_service(schedule=schedule)

        await svc.accrue_daily_fees(
            _PORTFOLIO, _FUND, Decimal("50000000"), date(2026, 3, 31)
        )

        svc._accrual_repo.insert.assert_called()


# ------------------------------------------------------------------
# crystallize_fees
# ------------------------------------------------------------------


class TestCrystallizeFees:
    @pytest.mark.asyncio
    async def test_crystallizes_on_quarter_end(self) -> None:
        schedule = _make_schedule(crystallization="quarterly")
        accruals = [
            _make_accrual(status=AccrualStatus.ACCRUED, nav_basis=Decimal("50000000")),
        ]
        svc = _make_service(schedule=schedule, accruals=accruals)

        await svc.crystallize_fees(
            _PORTFOLIO, _FUND, date(2026, 3, 31)  # quarter end
        )

        svc._accrual_repo.update_status.assert_called_once()
        call_args = svc._accrual_repo.update_status.call_args
        assert call_args.args[1] == AccrualStatus.CRYSTALLIZED

    @pytest.mark.asyncio
    async def test_skips_crystallization_mid_quarter(self) -> None:
        schedule = _make_schedule(crystallization="quarterly")
        svc = _make_service(schedule=schedule)

        await svc.crystallize_fees(
            _PORTFOLIO, _FUND, date(2026, 2, 15)  # mid-quarter
        )

        svc._accrual_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_hwm_on_crystallization(self) -> None:
        schedule = _make_schedule(crystallization="quarterly")
        accruals = [
            _make_accrual(status=AccrualStatus.ACCRUED, nav_basis=Decimal("52000000")),
        ]
        hwm = _make_hwm(hwm_nav=Decimal("50000000"), peak_nav=Decimal("50000000"))
        svc = _make_service(schedule=schedule, accruals=accruals, hwm=hwm)

        await svc.crystallize_fees(_PORTFOLIO, _FUND, date(2026, 3, 31))

        svc._hwm_repo.upsert.assert_called_once()
        new_hwm = svc._hwm_repo.upsert.call_args.args[0]
        assert new_hwm.hwm_nav == Decimal("52000000")

    @pytest.mark.asyncio
    async def test_no_op_without_schedule(self) -> None:
        svc = _make_service(schedule=None)

        await svc.crystallize_fees(_PORTFOLIO, _FUND, date(2026, 3, 31))

        svc._accrual_repo.update_status.assert_not_called()


# ------------------------------------------------------------------
# get_fee_summary
# ------------------------------------------------------------------


class TestGetFeeSummary:
    @pytest.mark.asyncio
    async def test_aggregates_by_fee_type(self) -> None:
        accruals = [
            _make_accrual(fee_type=FeeType.MANAGEMENT, accrued=Decimal("100")),
            _make_accrual(fee_type=FeeType.MANAGEMENT, accrued=Decimal("200")),
            _make_accrual(fee_type=FeeType.PERFORMANCE, accrued=Decimal("500")),
        ]
        svc = _make_service(accruals=accruals)

        summary = await svc.get_fee_summary(_PORTFOLIO)

        assert summary[FeeType.MANAGEMENT] == Decimal("300")
        assert summary[FeeType.PERFORMANCE] == Decimal("500")

    @pytest.mark.asyncio
    async def test_empty_summary(self) -> None:
        svc = _make_service(accruals=[])

        summary = await svc.get_fee_summary(_PORTFOLIO)

        assert summary == {}


# ------------------------------------------------------------------
# get_accruals
# ------------------------------------------------------------------


class TestGetAccruals:
    @pytest.mark.asyncio
    async def test_returns_accruals(self) -> None:
        accruals = [_make_accrual(), _make_accrual()]
        svc = _make_service(accruals=accruals)

        result = await svc.get_accruals(_PORTFOLIO)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_passes_date_filters(self) -> None:
        svc = _make_service()

        await svc.get_accruals(
            _PORTFOLIO, start=date(2026, 1, 1), end=date(2026, 3, 31)
        )

        svc._accrual_repo.get_by_portfolio.assert_called_once_with(
            _PORTFOLIO, start=date(2026, 1, 1), end=date(2026, 3, 31), session=None
        )
