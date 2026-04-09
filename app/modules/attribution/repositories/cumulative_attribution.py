"""Cumulative attribution persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.attribution.models.cumulative_attribution import CumulativeAttributionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CumulativeAttributionRepository(BaseRepository):
    """CRUD for CumulativeAttributionRecord."""

    async def save(
        self, record: CumulativeAttributionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> CumulativeAttributionRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CumulativeAttributionRecord)
                .where(CumulativeAttributionRecord.portfolio_id == str(portfolio_id))
                .order_by(CumulativeAttributionRecord.calculated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
