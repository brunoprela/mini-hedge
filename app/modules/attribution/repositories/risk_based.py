"""Risk-based attribution persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.attribution.models.risk_based import RiskBasedRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RiskBasedRepository(BaseRepository):
    """CRUD for RiskBasedRecord."""

    async def save(
        self,
        record: RiskBasedRecord,
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
    ) -> list[RiskBasedRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(RiskBasedRecord)
                .where(
                    RiskBasedRecord.portfolio_id == str(portfolio_id),
                    RiskBasedRecord.period_start >= start,
                    RiskBasedRecord.period_end <= end,
                )
                .order_by(RiskBasedRecord.period_start.asc())
            )
            return list(result.scalars().all())
