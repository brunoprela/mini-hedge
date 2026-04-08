"""Data access for fee accounting."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.fee_accounting.models import (
    FeeAccrualRecord,
    FeeScheduleRecord,
    HighWaterMarkRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeeScheduleRepository(BaseRepository):
    """CRUD for fee schedules."""

    async def get_by_fund_slug(
        self,
        fund_slug: str,
        *,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> FeeScheduleRecord | None:
        async with self._session(session) as session:
            stmt = select(FeeScheduleRecord).where(
                FeeScheduleRecord.fund_slug == fund_slug,
                FeeScheduleRecord.share_class == share_class,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_by_fund(
        self, fund_slug: str, *, session: AsyncSession | None = None
    ) -> list[FeeScheduleRecord]:
        """Get fee schedules for all share classes in a fund."""
        async with self._session(session) as session:
            stmt = (
                select(FeeScheduleRecord)
                .where(FeeScheduleRecord.fund_slug == fund_slug)
                .order_by(FeeScheduleRecord.share_class)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self, record: FeeScheduleRecord, *, session: AsyncSession | None = None
    ) -> FeeScheduleRecord:
        async with self._session(session) as session:
            existing = await session.execute(
                select(FeeScheduleRecord).where(
                    FeeScheduleRecord.fund_slug == record.fund_slug,
                    FeeScheduleRecord.share_class == record.share_class,
                )
            )
            existing_record = existing.scalar_one_or_none()
            if existing_record is not None:
                existing_record.management_fee_bps = record.management_fee_bps
                existing_record.performance_fee_pct = record.performance_fee_pct
                existing_record.hurdle_rate_pct = record.hurdle_rate_pct
                existing_record.high_water_mark = record.high_water_mark
                existing_record.crystallization_frequency = record.crystallization_frequency
                existing_record.payment_frequency = record.payment_frequency
                await session.flush()
                await session.commit()
                await session.refresh(existing_record)
                return existing_record
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record


class FeeAccrualRepository(BaseRepository):
    """CRUD for fee accruals."""

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        start: date | None = None,
        end: date | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[FeeAccrualRecord]:
        async with self._session(session) as session:
            stmt = select(FeeAccrualRecord).where(
                FeeAccrualRecord.portfolio_id == str(portfolio_id)
            )
            if start is not None:
                stmt = stmt.where(FeeAccrualRecord.accrual_date >= start)
            if end is not None:
                stmt = stmt.where(FeeAccrualRecord.accrual_date <= end)
            stmt = stmt.order_by(FeeAccrualRecord.accrual_date.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_by_type(
        self,
        portfolio_id: UUID,
        fee_type: str,
        *,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> FeeAccrualRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(FeeAccrualRecord)
                .where(
                    FeeAccrualRecord.portfolio_id == str(portfolio_id),
                    FeeAccrualRecord.fee_type == fee_type,
                    FeeAccrualRecord.share_class == share_class,
                )
                .order_by(FeeAccrualRecord.accrual_date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(
        self, record: FeeAccrualRecord, *, session: AsyncSession | None = None
    ) -> FeeAccrualRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def update_status(
        self,
        accrual_id: UUID,
        status: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            stmt = (
                update(FeeAccrualRecord)
                .where(FeeAccrualRecord.id == str(accrual_id))
                .values(status=status)
            )
            await session.execute(stmt)
            await session.commit()


class HighWaterMarkRepository(BaseRepository):
    """CRUD for high water marks."""

    async def get_latest(
        self,
        portfolio_id: UUID,
        *,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> HighWaterMarkRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(HighWaterMarkRecord)
                .where(
                    HighWaterMarkRecord.portfolio_id == str(portfolio_id),
                    HighWaterMarkRecord.share_class == share_class,
                )
                .order_by(HighWaterMarkRecord.hwm_date.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def upsert(
        self, record: HighWaterMarkRecord, *, session: AsyncSession | None = None
    ) -> HighWaterMarkRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record
