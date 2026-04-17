"""Fee schedule repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord
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

    async def list_by_fund(
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
