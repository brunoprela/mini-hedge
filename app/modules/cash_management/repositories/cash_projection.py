"""Cash projection persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.cash_management.models.cash_projection import CashProjectionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CashProjectionRepository(BaseRepository):
    async def insert(
        self, record: CashProjectionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> CashProjectionRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashProjectionRecord)
                .where(CashProjectionRecord.portfolio_id == str(portfolio_id))
                .order_by(CashProjectionRecord.projected_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
