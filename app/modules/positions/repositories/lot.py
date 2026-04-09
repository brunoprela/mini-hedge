"""Read model data access for lots."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.positions.models.lot import LotRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class LotRepository(BaseRepository):
    async def get_lots(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[LotRecord]:
        async with self._session(session) as session:
            stmt = (
                select(LotRecord)
                .where(
                    LotRecord.portfolio_id == str(portfolio_id),
                    LotRecord.instrument_id == instrument_id,
                )
                .order_by(LotRecord.acquired_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
