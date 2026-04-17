"""FX interest rate persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.fx_hedging.models.fx_interest_rate import FXInterestRateRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FXInterestRateRepository(BaseRepository):
    """CRUD for FX interest rates."""

    async def upsert(
        self,
        record: FXInterestRateRecord,
        *,
        session: AsyncSession | None = None,
    ) -> FXInterestRateRecord:
        async with self._session(session) as s:
            # Check if rate exists for this currency + tenor
            existing = await s.execute(
                select(FXInterestRateRecord).where(
                    FXInterestRateRecord.currency == record.currency,
                    FXInterestRateRecord.tenor_days == record.tenor_days,
                )
            )
            row = existing.scalar_one_or_none()
            if row is not None:
                row.rate = record.rate
                row.source = record.source
                row.updated_at = record.updated_at
                await s.flush()
                return row
            s.add(record)
            await s.flush()
            return record

    async def get_by_currency(
        self,
        currency: str,
        *,
        session: AsyncSession | None = None,
    ) -> FXInterestRateRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FXInterestRateRecord)
                .where(FXInterestRateRecord.currency == currency)
                .order_by(FXInterestRateRecord.updated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[FXInterestRateRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(FXInterestRateRecord).order_by(FXInterestRateRecord.currency)
            )
            return list(result.scalars().all())
