"""Fee accounting service — orchestrates accrual, crystallization, and queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.fee_accounting.core.calculator import (
    calculate_daily_management_fee,
    calculate_performance_fee,
    should_crystallize,
)
from app.modules.fee_accounting.interfaces import AccrualStatus, FeeType
from app.modules.fee_accounting.models.fee_accrual import FeeAccrualRecord
from app.modules.fee_accounting.models.high_water_mark import HighWaterMarkRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.fee_accounting.repositories.fee_accrual import FeeAccrualRepository
    from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
    from app.modules.fee_accounting.repositories.high_water_mark import HighWaterMarkRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()

_DEFAULT_SHARE_CLASS = "default"


class FeeAccountingService:
    """Manages fee accrual, crystallization, and reporting."""

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        schedule_repo: FeeScheduleRepository,
        accrual_repo: FeeAccrualRepository,
        hwm_repo: HighWaterMarkRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._schedule_repo = schedule_repo
        self._accrual_repo = accrual_repo
        self._hwm_repo = hwm_repo
        self._event_bus = event_bus

    async def accrue_daily_fees(
        self,
        portfolio_id: UUID,
        fund_slug: str,
        nav: Decimal,
        business_date: date,
        *,
        share_class: str = _DEFAULT_SHARE_CLASS,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        """Calculate and persist daily management + performance fee accruals."""
        schedule = await self._schedule_repo.get_by_fund_slug(
            fund_slug,
            share_class=share_class,
            session=session,
        )
        if schedule is None:
            # Fall back to default class schedule
            schedule = await self._schedule_repo.get_by_fund_slug(
                fund_slug,
                share_class=_DEFAULT_SHARE_CLASS,
                session=session,
            )
        if schedule is None:
            logger.warning("fee_schedule_not_found", fund_slug=fund_slug)
            return []

        accruals: list[FeeAccrualRecord] = []

        # --- Management fee ---
        mgmt_fee = calculate_daily_management_fee(nav, schedule.management_fee_bps)
        latest_mgmt = await self._accrual_repo.get_latest_by_type(
            portfolio_id,
            FeeType.MANAGEMENT,
            share_class=share_class,
            session=session,
        )
        cumulative_mgmt = latest_mgmt.cumulative_amount + mgmt_fee if latest_mgmt else mgmt_fee
        mgmt_accrual = FeeAccrualRecord(
            id=str(uuid4()),
            portfolio_id=str(portfolio_id),
            share_class=share_class,
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
        hwm_record = await self._hwm_repo.get_latest(
            portfolio_id,
            share_class=share_class,
            session=session,
        )
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
                portfolio_id,
                FeeType.PERFORMANCE,
                share_class=share_class,
                session=session,
            )
            cumulative_perf = latest_perf.cumulative_amount + perf_fee if latest_perf else perf_fee
            perf_accrual = FeeAccrualRecord(
                id=str(uuid4()),
                portfolio_id=str(portfolio_id),
                share_class=share_class,
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
            share_class=share_class,
            business_date=str(business_date),
            management_fee=str(mgmt_fee),
            performance_fee=str(perf_fee),
        )

        if self._event_bus is not None:
            from app.shared.schema_registry import fund_topic

            await self._event_bus.publish(
                fund_topic(fund_slug, "fees.accrued"),
                BaseEvent(
                    event_type=AuditEventType.FEES_ACCRUED,
                    data={
                        "portfolio_id": str(portfolio_id),
                        "share_class": share_class,
                        "business_date": str(business_date),
                        "management_fee": str(mgmt_fee),
                        "performance_fee": str(perf_fee),
                        "nav": str(nav),
                    },
                    fund_slug=fund_slug,
                    actor_id="eod-orchestrator",
                ),
            )

        return accruals

    async def crystallize_fees(
        self,
        portfolio_id: UUID,
        fund_slug: str,
        business_date: date,
        *,
        share_class: str = _DEFAULT_SHARE_CLASS,
        session: AsyncSession | None = None,
    ) -> None:
        """Mark accrued fees as crystallized and update the high water mark."""
        schedule = await self._schedule_repo.get_by_fund_slug(
            fund_slug,
            share_class=share_class,
            session=session,
        )
        if schedule is None:
            schedule = await self._schedule_repo.get_by_fund_slug(
                fund_slug,
                share_class=_DEFAULT_SHARE_CLASS,
                session=session,
            )
        if schedule is None:
            return

        if not should_crystallize(schedule.crystallization_frequency, business_date):
            return

        # Get all accrued (non-crystallized) records for this portfolio
        accruals = await self._accrual_repo.get_by_portfolio(portfolio_id, session=session)
        for accrual in accruals:
            if accrual.status == AccrualStatus.ACCRUED and accrual.share_class == share_class:
                await self._accrual_repo.update_status(
                    UUID(accrual.id), AccrualStatus.CRYSTALLIZED, session=session
                )

        # Update HWM to latest NAV basis
        class_accruals = [a for a in accruals if a.share_class == share_class]
        latest_accrual = class_accruals[0] if class_accruals else None
        if latest_accrual is not None:
            current_nav = latest_accrual.nav_basis
            hwm_record = await self._hwm_repo.get_latest(
                portfolio_id,
                share_class=share_class,
                session=session,
            )
            peak = max(current_nav, hwm_record.peak_nav) if hwm_record else current_nav
            new_hwm = HighWaterMarkRecord(
                id=str(uuid4()),
                portfolio_id=str(portfolio_id),
                share_class=share_class,
                hwm_date=business_date,
                hwm_nav=current_nav,
                peak_nav=peak,
            )
            await self._hwm_repo.upsert(new_hwm, session=session)

        logger.info(
            "fees_crystallized",
            portfolio_id=str(portfolio_id),
            share_class=share_class,
            business_date=str(business_date),
        )

        if self._event_bus is not None:
            from app.shared.schema_registry import fund_topic

            await self._event_bus.publish(
                fund_topic(fund_slug, "fees.crystallized"),
                BaseEvent(
                    event_type=AuditEventType.FEES_CRYSTALLIZED,
                    data={
                        "portfolio_id": str(portfolio_id),
                        "share_class": share_class,
                        "business_date": str(business_date),
                    },
                    fund_slug=fund_slug,
                    actor_id="eod-orchestrator",
                ),
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

    async def get_accruals_for_fund(
        self,
        portfolio_ids: list[UUID],
        start: date | None = None,
        end: date | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        """Query accrual history aggregated across a fund's portfolios."""
        all_records: list[FeeAccrualRecord] = []
        for pid in portfolio_ids:
            records = await self._accrual_repo.get_by_portfolio(
                pid, start=start, end=end, session=session
            )
            all_records.extend(records)
        # Sort by accrual_date descending to match single-portfolio behavior
        all_records.sort(key=lambda r: r.accrual_date, reverse=True)
        return all_records

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

    async def get_fund_summary(
        self,
        portfolio_ids: list[UUID],
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, Decimal]:
        """Return total accrued amount by fee type across all fund portfolios."""
        summary: dict[str, Decimal] = {}
        for pid in portfolio_ids:
            portfolio_summary = await self.get_fee_summary(pid, session=session)
            for fee_type, amount in portfolio_summary.items():
                summary[fee_type] = summary.get(fee_type, Decimal(0)) + amount
        return summary

    async def accrue_daily_for_fund(
        self,
        portfolio_ids: list[UUID],
        fund_slug: str,
        nav_per_portfolio: dict[UUID, Decimal] | None,
        business_date: date,
        *,
        share_class: str = _DEFAULT_SHARE_CLASS,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        """Run daily accrual across every portfolio in a fund.

        If `nav_per_portfolio` is None, uses Decimal(0) — callers should
        supply per-portfolio NAVs when available; otherwise accrual will
        still insert zero-amount records for audit/trace.
        """
        all_accruals: list[FeeAccrualRecord] = []
        for pid in portfolio_ids:
            nav = (nav_per_portfolio or {}).get(pid, Decimal(0))
            accruals = await self.accrue_daily_fees(
                pid,
                fund_slug,
                nav,
                business_date,
                share_class=share_class,
                session=session,
            )
            all_accruals.extend(accruals)
        return all_accruals

    async def crystallize_for_fund(
        self,
        portfolio_ids: list[UUID],
        fund_slug: str,
        business_date: date,
        *,
        share_class: str = _DEFAULT_SHARE_CLASS,
        session: AsyncSession | None = None,
    ) -> None:
        """Crystallize fees across every portfolio in a fund."""
        for pid in portfolio_ids:
            await self.crystallize_fees(
                pid,
                fund_slug,
                business_date,
                share_class=share_class,
                session=session,
            )

    async def approve_accruals(
        self,
        accrual_ids: list[UUID],
        *,
        actor_id: str = "system",
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> int:
        """Approve a batch of accrued fees — transition ACCRUED → CRYSTALLIZED.

        Validates each id exists and is in the ACCRUED state. Skips and
        logs accruals that are missing or already crystallized/paid so a
        replay or partially-applied batch does not raise.

        Publishes a single ``fee.approved`` event with the approved ids.
        Returns the count of accruals actually transitioned.
        """
        approved_ids: list[str] = []
        skipped: list[dict[str, str]] = []

        for accrual_id in accrual_ids:
            accrual = await self._accrual_repo.get_by_id(accrual_id, session=session)
            if accrual is None:
                skipped.append({"id": str(accrual_id), "reason": "not_found"})
                continue
            if accrual.status != AccrualStatus.ACCRUED:
                skipped.append(
                    {"id": str(accrual_id), "reason": f"invalid_state:{accrual.status}"}
                )
                continue
            await self._accrual_repo.update_status(
                accrual_id, AccrualStatus.CRYSTALLIZED, session=session
            )
            approved_ids.append(str(accrual_id))

        logger.info(
            "fee_accruals_approved",
            approved=len(approved_ids),
            skipped=len(skipped),
            skipped_details=skipped,
            actor_id=actor_id,
        )

        if approved_ids and self._event_bus is not None and fund_slug is not None:
            from app.shared.schema_registry import fund_topic

            await self._event_bus.publish(
                fund_topic(fund_slug, "fees.approved"),
                BaseEvent(
                    event_type=AuditEventType.FEES_APPROVED,
                    data={
                        "accrual_ids": approved_ids,
                        "count": len(approved_ids),
                    },
                    fund_slug=fund_slug,
                    actor_id=actor_id,
                ),
            )

        return len(approved_ids)
