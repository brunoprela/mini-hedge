"""Brinson-Fachler attribution result persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.attribution.models.brinson_fachler import BrinsonFachlerRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BrinsonFachlerRepository(BaseRepository):
    """CRUD for BrinsonFachlerRecord."""

    async def save(
        self,
        record: BrinsonFachlerRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[BrinsonFachlerRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(BrinsonFachlerRecord)
                .where(
                    BrinsonFachlerRecord.portfolio_id == str(portfolio_id),
                    BrinsonFachlerRecord.period_start >= start,
                    BrinsonFachlerRecord.period_end <= end,
                )
                .order_by(BrinsonFachlerRecord.period_start.asc())
            )
            return list(result.scalars().all())
