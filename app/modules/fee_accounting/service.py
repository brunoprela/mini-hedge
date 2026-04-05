"""Fee accounting service — orchestrates accrual, crystallization, and queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.fee_accounting.calculator import (
    calculate_daily_management_fee,
    calculate_performance_fee,
    should_crystallize,
)
from app.modules.fee_accounting.interface import AccrualStatus, FeeType
from app.modules.fee_accounting.models import FeeAccrualRecord, HighWaterMarkRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.fee_accounting.repository import (
        FeeAccrualRepository,
        FeeScheduleRepository,
        HighWaterMarkRepository,
    )
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


class FeeAccountingService:
    """Manages fee accrual, crystallization, and reporting."""

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        schedule_repo: FeeScheduleRepository,
        accrual_repo: FeeAccrualRepository,
        hwm_repo: HighWaterMarkRepository,
    ) -> None:
        self._session_factory = session_factory
        self._schedule_repo = schedule_repo
        self._accrual_repo = accrual_repo
        self._hwm_repo = hwm_repo

    async def accrue_daily_fees(
        self,
        portfolio_id: UUID,
        fund_slug: str,
        nav: Decimal,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        """Calculate and persist daily management + performance fee accruals."""
        schedule = await self._schedule_repo.get_by_fund_slug(fund_slug, session=session)
        if schedule is None:
            logger.warning("fee_schedule_not_found", fund_slug=fund_slug)
            return []

        accruals: list[FeeAccrualRecord] = []

        # --- Management fee ---
        mgmt_fee = calculate_daily_management_fee(nav, schedule.management_fee_bps)
        latest_mgmt = await self._accrual_repo.get_latest_by_type(
            portfolio_id, FeeType.MANAGEMENT, session=session
        )
        cumulative_mgmt = latest_mgmt.cumulative_amount + mgmt_fee if latest_mgmt else mgmt_fee
        mgmt_accrual = FeeAccrualRecord(
            id=str(uuid4()),
            portfolio_id=str(portfolio_id),
            fee_type=FeeType.MANAGEMENT,
            accrual_date=business_date,
            nav_basis=nav,
            accrued_amount=mgmt_fee,
            cumulative_amount=cumulative_mgmt,
            status=AccrualStatus.ACCRUED,
        )
        mgmt_accrual = await self._accrual_repo.insert(mgmt_accrual, session=session)
        accruals.append(mgmt_accrual)

        # --- Performance fee ---
        hwm_record = await self._hwm_repo.get_latest(portfolio_id, session=session)
        hwm_nav = hwm_record.hwm_nav if hwm_record else nav
        days_since_hwm = (business_date - hwm_record.hwm_date).days if hwm_record else 0

        perf_fee = calculate_performance_fee(
            current_nav=nav,
            hwm_nav=hwm_nav,
            pct=schedule.performance_fee_pct,
            hurdle_annual=schedule.hurdle_rate_pct,
            days=days_since_hwm,
        )
        if perf_fee > 0:
            latest_perf = await self._accrual_repo.get_latest_by_type(
                portfolio_id, FeeType.PERFORMANCE, session=session
            )
            cumulative_perf = latest_perf.cumulative_amount + perf_fee if latest_perf else perf_fee
            perf_accrual = FeeAccrualRecord(
                id=str(uuid4()),
                portfolio_id=str(portfolio_id),
                fee_type=FeeType.PERFORMANCE,
                accrual_date=business_date,
                nav_basis=nav,
                accrued_amount=perf_fee,
                cumulative_amount=cumulative_perf,
                status=AccrualStatus.ACCRUED,
            )
            perf_accrual = await self._accrual_repo.insert(perf_accrual, session=session)
            accruals.append(perf_accrual)

        logger.info(
            "fees_accrued",
            portfolio_id=str(portfolio_id),
            business_date=str(business_date),
            management_fee=str(mgmt_fee),
            performance_fee=str(perf_fee),
        )
        return accruals

    async def crystallize_fees(
        self,
        portfolio_id: UUID,
        fund_slug: str,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Mark accrued fees as crystallized and update the high water mark."""
        schedule = await self._schedule_repo.get_by_fund_slug(fund_slug, session=session)
        if schedule is None:
            return

        if not should_crystallize(schedule.crystallization_frequency, business_date):
            return

        # Get all accrued (non-crystallized) records for this portfolio
        accruals = await self._accrual_repo.get_by_portfolio(portfolio_id, session=session)
        for accrual in accruals:
            if accrual.status == AccrualStatus.ACCRUED:
                await self._accrual_repo.update_status(
                    UUID(accrual.id), AccrualStatus.CRYSTALLIZED, session=session
                )

        # Update HWM to latest NAV basis
        latest_accrual = accruals[0] if accruals else None
        if latest_accrual is not None:
            current_nav = latest_accrual.nav_basis
            hwm_record = await self._hwm_repo.get_latest(portfolio_id, session=session)
            peak = max(current_nav, hwm_record.peak_nav) if hwm_record else current_nav
            new_hwm = HighWaterMarkRecord(
                id=str(uuid4()),
                portfolio_id=str(portfolio_id),
                hwm_date=business_date,
                hwm_nav=current_nav,
                peak_nav=peak,
            )
            await self._hwm_repo.upsert(new_hwm, session=session)

        logger.info(
            "fees_crystallized",
            portfolio_id=str(portfolio_id),
            business_date=str(business_date),
        )

    async def get_accruals(
        self,
        portfolio_id: UUID,
        start: date | None = None,
        end: date | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        """Query accrual history for a portfolio."""
        return await self._accrual_repo.get_by_portfolio(
            portfolio_id, start=start, end=end, session=session
        )

    async def get_fee_summary(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, Decimal]:
        """Return total accrued amount by fee type."""
        accruals = await self._accrual_repo.get_by_portfolio(portfolio_id, session=session)
        summary: dict[str, Decimal] = {}
        for accrual in accruals:
            fee_type = accrual.fee_type
            summary[fee_type] = summary.get(fee_type, Decimal(0)) + accrual.accrued_amount
        return summary
