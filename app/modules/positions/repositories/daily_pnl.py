"""Daily P&L repository."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.positions.models.daily_pnl import DailyPnLRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DailyPnLRepository(BaseRepository):
    """CRUD for positions.daily_pnl snapshots."""

    async def get_by_portfolio(
        self,
        portfolio_id: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[DailyPnLRecord]:
        async with self._session(session) as session:
            stmt = select(DailyPnLRecord).where(
                DailyPnLRecord.portfolio_id == portfolio_id
            )
            if from_date is not None:
                stmt = stmt.where(DailyPnLRecord.business_date >= from_date)
            if to_date is not None:
                stmt = stmt.where(DailyPnLRecord.business_date <= to_date)
            stmt = stmt.order_by(DailyPnLRecord.business_date.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_date(
        self,
        business_date: date,
        *,
        portfolio_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[DailyPnLRecord]:
        async with self._session(session) as session:
            stmt = select(DailyPnLRecord).where(
                DailyPnLRecord.business_date == business_date
            )
            if portfolio_id is not None:
                stmt = stmt.where(DailyPnLRecord.portfolio_id == portfolio_id)
            stmt = stmt.order_by(DailyPnLRecord.instrument_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self, record: DailyPnLRecord, *, session: AsyncSession | None = None
    ) -> DailyPnLRecord:
        async with self._session(session) as session:
            merged = await session.merge(record)
            await session.flush()
            await session.commit()
            await session.refresh(merged)
            return merged

    async def upsert_batch(
        self, records: list[DailyPnLRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.flush()
            await session.commit()
