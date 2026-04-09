"""Trade decision repository."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.compliance.models.trade_decision import TradeDecisionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TradeDecisionRepository(BaseRepository):
    """Append-only log of trade compliance decisions."""

    async def insert(
        self, record: TradeDecisionRecord, *, session: AsyncSession | None = None
    ) -> TradeDecisionRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_portfolio(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[TradeDecisionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(TradeDecisionRecord)
                .where(TradeDecisionRecord.portfolio_id == str(portfolio_id))
                .order_by(TradeDecisionRecord.decided_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
